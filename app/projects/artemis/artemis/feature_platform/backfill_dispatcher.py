from __future__ import annotations

import threading
from typing import Any, Callable
from uuid import uuid4

from artemis.consts import TaskCode, TaskMode
from artemis.core.task_engine import TaskEngine
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.registry.client import FeatureRegistryClient
from artemis.models import TaskRunReq


RegistryFactory = Callable[[str], FeatureRegistryClient]


class BackfillDispatcher:
    """Claims persisted backfill runs and hands them to the existing TaskEngine."""

    def __init__(
        self,
        task_engine: TaskEngine,
        registry_factory: RegistryFactory,
        settings_factory: Callable[[], Any],
    ) -> None:
        self.task_engine = task_engine
        self.registry_factory = registry_factory
        self.settings_factory = settings_factory
        self.worker_id = f"artemis-backfill:{uuid4()}"
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._profiles: set[str] = {"default"}
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="feature-backfill-dispatcher",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5)
        self._thread = None

    def wake(self, source_profile: str = "default") -> None:
        self._profiles.add(source_profile)
        self._wake.set()

    def dispatch_once(self, source_profile: str = "default") -> int:
        settings = self.settings_factory()
        client = self.registry_factory(source_profile)
        dispatched = 0
        for status in ("running", "queued"):
            page = client.list_backfills(
                status=status,
                source_profile=source_profile,
                limit=500,
            )
            for job in page.get("items") or []:
                while dispatched < settings.backfill_global_max_concurrency:
                    detail = client.claim_backfill_run(
                        str(job["backfill_id"]),
                        worker_id=self.worker_id,
                        global_max_concurrency=settings.backfill_global_max_concurrency,
                    )
                    if not detail:
                        break
                    self._submit_claimed(client, detail)
                    dispatched += 1
        return dispatched

    def cancel(
        self,
        source_profile: str,
        backfill_id: str,
    ) -> dict[str, Any]:
        client = self.registry_factory(source_profile)
        detail = client.get_backfill(backfill_id)
        for run in detail.get("runs") or []:
            if run.get("status") in {"planning", "running", "validating"}:
                self.task_engine.cancel_task(str(run["run_id"]))
        result = client.cancel_backfill(backfill_id)
        self.wake(source_profile)
        return result

    def _submit_claimed(self, client: FeatureRegistryClient, detail: dict[str, Any]) -> None:
        run = dict(detail.get("run") or {})
        payload = dict(run.get("request_payload") or {})
        snapshot = dict(payload.get("dependency_plan_snapshot") or {})
        root_ids = {int(value) for value in payload.get("root_feature_version_ids") or []}
        root_features = [
            {"code": node["feature_code"], "version": int(node["version_number"])}
            for node in snapshot.get("nodes") or []
            if int(node.get("feature_version_id") or 0) in root_ids
        ]
        if len(root_features) != len(root_ids):
            client.fail_run(
                str(run["run_id"]),
                "BACKFILL_PLAN_SNAPSHOT_INVALID",
                "claimed backfill run has no complete immutable root snapshot",
            )
            return
        task_request = TaskRunReq.model_validate(
            {
                "meta": {
                    "run_id": run["run_id"],
                    "task_id": run["run_id"],
                    "exec_type": TaskMode.ASYNC.value,
                    "task_code": TaskCode.FEATURE_PLATFORM_COMPUTE.value,
                },
                "body": {
                    "run_id": run["run_id"],
                    "root_features": root_features,
                    "root_feature_version_ids": sorted(root_ids),
                    "expected_plan_checksum": payload["dependency_plan_checksum"],
                    "security_ids": [
                        int(subject["security_id"])
                        for subject in detail.get("subjects") or []
                    ],
                    "as_of_time": run["as_of_time"],
                    "data_cutoff_time": run["data_cutoff_time"],
                    "source_profile": run["source_profile"],
                    "market": run["market"],
                    "parameters": {},
                    "preclaimed": True,
                },
            }
        )
        try:
            self.task_engine.run(task_request)
        except Exception as exc:
            client.fail_run(
                str(run["run_id"]),
                "BACKFILL_TASK_SUBMIT_FAILED",
                str(exc),
            )

    def _loop(self) -> None:
        while not self._stop.is_set():
            for profile in tuple(self._profiles):
                try:
                    self.dispatch_once(profile)
                except FeaturePlatformError:
                    pass
                except Exception:
                    pass
            interval = self.settings_factory().backfill_dispatch_interval_seconds
            self._wake.wait(interval)
            self._wake.clear()

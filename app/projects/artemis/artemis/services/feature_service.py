from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from artemis.consts import TaskCode, TaskMode
from artemis.core import cfg_mgr
from artemis.core.task_engine import TaskEngine
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import (
    FeatureComputeRequest,
    FeatureComputeResponse,
    ManifestSelectionRequest,
    ManifestValidateRequest,
)
from artemis.feature_platform.manifests.checksum import manifest_registry_checksum
from artemis.feature_platform.manifests.loader import FeatureManifestLoader
from artemis.feature_platform.manifests.validator import validate_manifest
from artemis.feature_platform.planning import DependencyPlanner
from artemis.feature_platform.registry.client import FeatureRegistryClient
from artemis.feature_platform.registry.factory import build_registry_client
from artemis.models import TaskRunReq
from artemis.telemetry.otel import record_feature_stale_runs


RegistryFactory = Callable[[str], FeatureRegistryClient]


def _code_revision() -> str:
    configured = os.getenv("ARTEMIS_CODE_REVISION", "").strip()
    if configured:
        return configured
    repository = Path(__file__).resolve().parents[5]
    try:
        revision = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=no"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        if revision:
            return revision + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        pass
    return "artemis-0.1.0-unknown"


def _universe_hash(security_ids: list[int]) -> str:
    canonical = json.dumps(sorted(security_ids), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class FeatureService:
    def __init__(
        self,
        task_engine: TaskEngine,
        *,
        registry_factory: RegistryFactory | None = None,
        code_revision: str | None = None,
    ) -> None:
        self.task_engine = task_engine
        self.registry_factory = registry_factory or (lambda profile: build_registry_client(profile))
        self.code_revision = code_revision

    @staticmethod
    def _settings():
        return cfg_mgr.engine_config().feature_platform

    def _ensure_enabled(self) -> None:
        if not self._settings().enabled:
            raise FeaturePlatformError(
                "FEATURE_PLATFORM_DISABLED",
                "Feature Platform execution is disabled",
                status_code=503,
            )

    def _loader(self) -> FeatureManifestLoader:
        return FeatureManifestLoader(self._settings().manifest_root)

    def validate_manifests(self, request: ManifestValidateRequest) -> dict[str, Any]:
        loader = self._loader()
        if request.manifests:
            manifests = loader.load_inline(
                request.manifests,
                check_entrypoints=request.check_entrypoints,
            )
        else:
            manifests = loader.load(
                request.paths,
                check_entrypoints=request.check_entrypoints,
            ).manifests
        return {
            "valid": True,
            "count": len(manifests),
            "manifests": [
                validate_manifest(manifest, check_entrypoint=request.check_entrypoints)
                for manifest in manifests
            ],
        }

    def sync_registry(self, request: ManifestSelectionRequest) -> dict[str, Any]:
        self._ensure_enabled()
        catalog = self._loader().load(
            request.paths,
            check_entrypoints=request.check_entrypoints,
        )
        return self.registry_factory(request.source_profile).sync_manifests(catalog.manifests)

    def compute(self, request: FeatureComputeRequest) -> FeatureComputeResponse:
        self._ensure_enabled()
        catalog = self._loader().load(check_entrypoints=True)
        client = self.registry_factory(request.source_profile)
        plan = DependencyPlanner(client.resolve_version).build(request.features)
        plan.ensure_executable()

        for node in plan.ordered_nodes:
            manifest = catalog.get(
                node.registry_version.feature_code,
                node.registry_version.version_number,
            )
            local_checksum = manifest_registry_checksum(manifest)
            if local_checksum != node.registry_version.manifest_checksum:
                raise FeaturePlatformError(
                    "MANIFEST_CHECKSUM_CONFLICT",
                    (
                        f"local manifest {manifest.identity} checksum {local_checksum} does not match "
                        f"published registry checksum {node.registry_version.manifest_checksum}"
                    ),
                    status_code=409,
                )

        parameters = dict(request.parameters)
        if request.idempotency_key:
            parameters["idempotency_key"] = request.idempotency_key
        create_payload: dict[str, Any] = {
            "request_fingerprint": "",
            "producer_service": "artemis",
            "trigger_type": request.trigger_type,
            "as_of_time": request.as_of_time.isoformat(),
            "data_cutoff_time": request.data_cutoff_time.isoformat(),
            "source_profile": request.source_profile,
            "market": request.market,
            "universe_hash": _universe_hash(request.security_ids),
            "code_revision": self.code_revision or _code_revision(),
            "root_feature_version_ids": list(plan.root_version_ids),
            "dependency_plan_checksum": plan.plan_checksum,
            "parameters": parameters,
            "force": request.force or bool(request.retry_of_run_id),
        }
        if request.idempotency_key:
            create_payload["producer_run_ref"] = request.idempotency_key
        if request.retry_of_run_id:
            create_payload["retry_of_run_id"] = request.retry_of_run_id

        created = client.create_run(create_payload)
        response = FeatureComputeResponse.model_validate(created)
        if response.reused:
            return response

        try:
            client.batch_subjects(response.run_id, request.security_ids, "feature_compute_request")
            task_request = TaskRunReq.model_validate(
                {
                    "meta": {
                        "run_id": response.run_id,
                        "task_id": response.run_id,
                        "exec_type": TaskMode.ASYNC.value,
                        "task_code": TaskCode.FEATURE_PLATFORM_COMPUTE.value,
                    },
                    "body": {
                        "run_id": response.run_id,
                        "root_features": [item.model_dump(mode="json") for item in request.features],
                        "root_feature_version_ids": list(plan.root_version_ids),
                        "expected_plan_checksum": plan.plan_checksum,
                        "security_ids": request.security_ids,
                        "as_of_time": request.as_of_time.isoformat(),
                        "data_cutoff_time": request.data_cutoff_time.isoformat(),
                        "source_profile": request.source_profile,
                        "market": request.market,
                        "parameters": parameters,
                    },
                }
            )
            self.task_engine.run(task_request)
        except Exception:
            try:
                client.cancel_run(response.run_id)
            except Exception:
                pass
            raise
        return response

    def get_execution(self, run_id: str, source_profile: str = "default") -> dict[str, Any]:
        self._ensure_enabled()
        return self.registry_factory(source_profile).get_run(run_id, include_subjects=True)

    def reconcile_stale_runs(
        self,
        source_profile: str = "default",
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        timeout = self._settings().stale_run_timeout_seconds
        current = now or datetime.now(timezone.utc)
        stale_before = current.astimezone(timezone.utc) - timedelta(seconds=timeout)
        result = self.registry_factory(source_profile).reconcile_stale_runs(stale_before)
        record_feature_stale_runs(int(result.get("aborted_count", 0)))
        return result

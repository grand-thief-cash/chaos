from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from artemis.core import cfg_mgr
from artemis.engines.task_engine.base import BaseTaskUnit
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureReference, FeatureNumericOutput
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.execution.output_validator import OutputValidator, ValidatedOutput
from artemis.feature_platform.execution.python_executor import PythonFeatureExecutor
from artemis.feature_platform.execution.runner import FeatureRunner
from artemis.feature_platform.manifests.checksum import manifest_registry_checksum
from artemis.feature_platform.manifests.loader import FeatureManifestLoader, LoadedCatalog
from artemis.feature_platform.planning import DependencyPlanner, ExecutionPlan
from artemis.feature_platform.providers.phoenixa import PhoenixAFeatureProvider
from artemis.feature_platform.registry.client import FeatureRegistryClient
from artemis.feature_platform.registry.factory import build_registry_client
from artemis.feature_platform.storage.phoenixa_writer import PhoenixAFeatureWriter
from artemis.telemetry.otel import record_feature_item, record_feature_run, record_feature_values


class _TaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    root_features: list[FeatureReference] = Field(min_length=1)
    root_feature_version_ids: list[StrictInt] = Field(min_length=1)
    expected_plan_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    security_ids: list[StrictInt] = Field(min_length=1)
    as_of_time: datetime
    data_cutoff_time: datetime
    source_profile: str
    market: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("root_feature_version_ids", "security_ids")
    @classmethod
    def validate_positive_unique(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value) or len(value) != len(set(value)):
            raise ValueError("ids must be unique positive integers")
        return value

    @field_validator("as_of_time", "data_cutoff_time")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run times must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_cutoff(self) -> "_TaskPayload":
        if self.data_cutoff_time > self.as_of_time:
            raise ValueError("data_cutoff_time must not be later than as_of_time")
        return self


class FeatureComputeTask(BaseTaskUnit):
    """TaskEngine adapter for a frozen PhoenixA Feature Run."""

    def __init__(self) -> None:
        self.payload: _TaskPayload | None = None
        self.client: FeatureRegistryClient | None = None
        self.catalog: LoadedCatalog | None = None
        self.plan: ExecutionPlan | None = None
        self.runner: FeatureRunner | None = None
        self.provider: PhoenixAFeatureProvider | None = None
        self.writer: PhoenixAFeatureWriter | None = None
        self.results: dict[int, ValidatedOutput] = {}
        self.outputs: dict[int, FeatureNumericOutput] = {}
        self.item_states: dict[int, str] = {}
        self.item_durations: dict[int, int] = {}
        self.requires_availability: dict[int, bool] = {}
        self.remote_status = "queued"
        self.current_feature_version_id: int | None = None
        self._remote_lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def _require_state(self) -> tuple[_TaskPayload, FeatureRegistryClient, LoadedCatalog, ExecutionPlan]:
        if not self.payload or not self.client or not self.catalog or not self.plan:
            raise FeaturePlatformError("INTERNAL_ERROR", "feature task was not initialized")
        return self.payload, self.client, self.catalog, self.plan

    def _update_remote_run(
        self,
        expected_status: str,
        new_status: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not self.payload or not self.client:
            raise FeaturePlatformError("INTERNAL_ERROR", "feature task registry client is unavailable")
        with self._remote_lock:
            result = self.client.update_run(
                self.payload.run_id,
                expected_status,
                new_status,
                **kwargs,
            )
            self.remote_status = str(result.get("status", new_status))
            return result

    def _start_heartbeat(self, ctx) -> None:
        if self._heartbeat_thread is not None:
            return
        interval = cfg_mgr.engine_config().feature_platform.heartbeat_interval_seconds
        self._heartbeat_stop.clear()

        def heartbeat_loop() -> None:
            while not self._heartbeat_stop.wait(interval):
                with self._remote_lock:
                    status = self.remote_status
                    if status not in {"planning", "running", "validating"} or not self.payload or not self.client:
                        return
                    try:
                        self.client.update_run(
                            self.payload.run_id,
                            status,
                            status,
                            heartbeat_at=datetime.now(timezone.utc),
                        )
                    except Exception as exc:
                        if ctx.logger:
                            ctx.logger.warning(
                                {
                                    "event": "feature_run_heartbeat_failed",
                                    "run_id": self.payload.run_id,
                                    "status": status,
                                    "error": str(exc),
                                }
                            )

        self._heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            name=f"feature-heartbeat-{self.payload.run_id if self.payload else 'unknown'}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)
        self._heartbeat_thread = None

    def _feature_code(self, version_id: int) -> str:
        if not self.plan:
            return "unknown"
        for node in self.plan.ordered_nodes:
            if node.id == version_id:
                return node.registry_version.feature_code
        return "unknown"

    def parameter_check(self, ctx) -> None:
        settings = cfg_mgr.engine_config().feature_platform
        if not settings.enabled:
            raise FeaturePlatformError("FEATURE_PLATFORM_DISABLED", "Feature Platform execution is disabled")
        try:
            self.payload = _TaskPayload.model_validate(ctx.incoming_params)
        except Exception as exc:
            raise FeaturePlatformError("RUN_PAYLOAD_INVALID", f"invalid feature task payload: {exc}") from exc
        if str(ctx.run_id) != self.payload.run_id:
            raise FeaturePlatformError(
                "RUN_ID_MISMATCH",
                f"TaskEngine run_id {ctx.run_id} does not match feature run {self.payload.run_id}",
            )

    def load_dynamic_parameters(self, ctx) -> dict[str, Any]:
        if self.payload is None:
            raise FeaturePlatformError("INTERNAL_ERROR", "feature task payload is unavailable")
        injected = getattr(ctx, "feature_registry_client", None)
        self.client = injected or build_registry_client(self.payload.source_profile, ctx.logger)
        settings = cfg_mgr.engine_config().feature_platform
        self.catalog = FeatureManifestLoader(settings.manifest_root).load(check_entrypoints=True)
        return {}

    def before_execute(self, ctx) -> None:
        if not self.payload or not self.client or not self.catalog:
            raise FeaturePlatformError("INTERNAL_ERROR", "feature task dependencies are unavailable")
        self._update_remote_run(
            "queued",
            "planning",
            worker_id=f"artemis:{ctx.task_id}",
            heartbeat_at=datetime.now(timezone.utc),
        )
        self._start_heartbeat(ctx)
        self.plan = DependencyPlanner(self.client.resolve_version).build(self.payload.root_features)
        self.plan.ensure_executable()
        if self.plan.plan_checksum != self.payload.expected_plan_checksum:
            raise FeaturePlatformError(
                "DEPENDENCY_PLAN_CHECKSUM_MISMATCH",
                "replanned dependency graph differs from the frozen run plan",
            )
        if list(self.plan.root_version_ids) != sorted(self.payload.root_feature_version_ids):
            raise FeaturePlatformError(
                "RUN_ITEM_PLAN_MISMATCH",
                "replanned root feature version ids differ from the frozen run roots",
            )

        for node in self.plan.ordered_nodes:
            manifest = self.catalog.get(
                node.registry_version.feature_code,
                node.registry_version.version_number,
            )
            if manifest_registry_checksum(manifest) != node.registry_version.manifest_checksum:
                raise FeaturePlatformError(
                    "MANIFEST_CHECKSUM_CONFLICT",
                    f"local manifest {manifest.identity} differs from the published registry version",
                )
            upstream_requires = any(
                self.requires_availability.get(upstream_id, False)
                for upstream_id in node.feature_dependency_ids
            )
            self.requires_availability[node.id] = bool(node.data_field_dependencies) or upstream_requires

        self.client.batch_items(self.payload.run_id, self.plan.feature_version_ids)
        self.item_states = {version_id: "queued" for version_id in self.plan.feature_version_ids}
        settings = cfg_mgr.engine_config().feature_platform
        self.runner = FeatureRunner(
            PythonFeatureExecutor(settings.plugin_timeout_seconds),
            OutputValidator(),
        )
        self.provider = PhoenixAFeatureProvider(self.client)
        self.writer = PhoenixAFeatureWriter(self.client, settings.write_batch_size)
        ctx.stats["execution_plan"] = self.plan.summary()

    def execute(self, ctx) -> dict[int, ValidatedOutput]:
        payload, client, catalog, plan = self._require_state()
        if not self.runner or not self.provider:
            raise FeaturePlatformError("INTERNAL_ERROR", "feature runner is unavailable")
        self._update_remote_run(
            "planning",
            "running",
            worker_id=f"artemis:{ctx.task_id}",
            heartbeat_at=datetime.now(timezone.utc),
        )

        for node in plan.ordered_nodes:
            self.current_feature_version_id = node.id
            client.update_item(payload.run_id, node.id, "queued", "running")
            self.item_states[node.id] = "running"
            started = time.monotonic()
            manifest = catalog.get(
                node.registry_version.feature_code,
                node.registry_version.version_number,
            )
            if ctx.logger:
                ctx.logger.info(
                    {
                        "event": "feature_plugin_started",
                        "run_id": payload.run_id,
                        "feature_code": node.registry_version.feature_code,
                        "feature_version_id": node.id,
                        "producer_service": "artemis",
                        "source_profile": payload.source_profile,
                        "as_of_time": payload.as_of_time.isoformat(),
                        "data_cutoff_time": payload.data_cutoff_time.isoformat(),
                        "phase": "execute",
                        "status": "running",
                    }
                )
            dependency_outputs = {
                upstream_id: self.outputs[upstream_id]
                for upstream_id in node.feature_dependency_ids
            }
            execution_context = FeatureExecutionContext(
                run_id=payload.run_id,
                node=node,
                manifest=manifest,
                as_of_time=payload.as_of_time,
                data_cutoff_time=payload.data_cutoff_time,
                security_ids=tuple(payload.security_ids),
                source_profile=payload.source_profile,
                market=payload.market,
                parameters=dict(payload.parameters),
                dependency_outputs=dependency_outputs,
            )
            validated = self.runner.compute(
                execution_context,
                self.provider,
                requires_source_availability=self.requires_availability[node.id],
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            client.update_item(
                payload.run_id,
                node.id,
                "running",
                "validating",
                input_count=validated.input_count,
                output_count=validated.output_count,
                valid_count=validated.valid_count,
                missing_count=validated.missing_count,
                invalid_count=validated.invalid_count,
                duration_ms=duration_ms,
                quality_summary=validated.quality_summary(),
            )
            self.item_states[node.id] = "validating"
            self.item_durations[node.id] = duration_ms
            self.results[node.id] = validated
            self.outputs[node.id] = validated.output
            if ctx.logger:
                ctx.logger.info(
                    {
                        "event": "feature_plugin_validated",
                        "run_id": payload.run_id,
                        "feature_code": node.registry_version.feature_code,
                        "feature_version_id": node.id,
                        "phase": "validating",
                        "status": "succeeded",
                        "duration_ms": duration_ms,
                        **validated.quality_summary(),
                    }
                )
        self.current_feature_version_id = None
        return self.results

    def post_process(self, ctx, result: dict[int, ValidatedOutput]) -> dict[int, ValidatedOutput]:
        _, _, _, plan = self._require_state()
        if set(result) != set(plan.feature_version_ids):
            raise FeaturePlatformError(
                "OUTPUT_SCHEMA_INVALID",
                "not every planned feature node produced a validated output",
            )
        return result

    def sink(self, ctx, processed: dict[int, ValidatedOutput]) -> None:
        payload, client, _, plan = self._require_state()
        if not self.writer:
            raise FeaturePlatformError("INTERNAL_ERROR", "feature writer is unavailable")
        total_written = 0
        item_stats: list[dict[str, Any]] = []
        for node in plan.ordered_nodes:
            self.current_feature_version_id = node.id
            validated = processed[node.id]
            written = self.writer.write(payload.run_id, validated)
            total_written += written
            client.update_item(
                payload.run_id,
                node.id,
                "validating",
                "succeeded",
                input_count=validated.input_count,
                output_count=validated.output_count,
                valid_count=validated.valid_count,
                missing_count=validated.missing_count,
                invalid_count=validated.invalid_count,
                duration_ms=self.item_durations[node.id],
                quality_summary=validated.quality_summary(),
            )
            self.item_states[node.id] = "succeeded"
            quality = validated.quality_summary()
            item_stats.append(
                {
                    "feature_code": node.registry_version.feature_code,
                    "feature_version_id": node.id,
                    "duration_ms": self.item_durations[node.id],
                    "values_written": written,
                    **quality,
                }
            )
            record_feature_item(
                node.registry_version.feature_code,
                "succeeded",
                self.item_durations[node.id],
                validated.coverage_ratio,
            )
            record_feature_values(node.registry_version.feature_code, "succeeded", written)
            if ctx.logger:
                ctx.logger.info(
                    {
                        "event": "feature_values_written",
                        "run_id": payload.run_id,
                        "feature_code": node.registry_version.feature_code,
                        "feature_version_id": node.id,
                        "phase": "sink",
                        "status": "succeeded",
                        "values_written": written,
                    }
                )
        self.current_feature_version_id = None
        ctx.stats["numeric_values_written"] = total_written
        ctx.stats["feature_items"] = item_stats

    def finalize(self, ctx) -> None:
        payload, client, _, _ = self._require_state()
        self._update_remote_run(
            "running",
            "validating",
            heartbeat_at=datetime.now(timezone.utc),
        )
        self._stop_heartbeat()
        completed = client.complete_run(payload.run_id)
        self.remote_status = str(completed.get("status", "succeeded"))
        if self.remote_status != "succeeded":
            raise FeaturePlatformError(
                "RUN_COMPLETION_FAILED",
                f"feature run completed with unexpected status {self.remote_status}",
            )
        for version_id in self.plan.root_version_ids:
            record_feature_run(self._feature_code(version_id), "succeeded")
        if ctx.logger:
            ctx.logger.info(
                {
                    "event": "feature_run_completed",
                    "run_id": payload.run_id,
                    "producer_service": "artemis",
                    "source_profile": payload.source_profile,
                    "as_of_time": payload.as_of_time.isoformat(),
                    "data_cutoff_time": payload.data_cutoff_time.isoformat(),
                    "phase": "finalize",
                    "status": self.remote_status,
                }
            )

    def _cleanup_failed_run(self, ctx, exc: Exception) -> None:
        self._stop_heartbeat()
        if not self.payload or not self.client:
            return
        error_code = exc.code if isinstance(exc, FeaturePlatformError) else "INTERNAL_ERROR"
        context = f"run_id={self.payload.run_id}"
        if self.current_feature_version_id:
            context += f" feature_version_id={self.current_feature_version_id}"
        message = f"{context}: {exc}"
        for version_id, state in list(self.item_states.items()):
            try:
                terminal_status: str | None = None
                if state == "queued":
                    self.client.update_item(
                        self.payload.run_id,
                        version_id,
                        "queued",
                        "skipped",
                        error_code=error_code,
                        error_message=message,
                    )
                    self.item_states[version_id] = "skipped"
                    terminal_status = "skipped"
                elif state in {"running", "validating"}:
                    validated = self.results.get(version_id)
                    self.client.update_item(
                        self.payload.run_id,
                        version_id,
                        state,
                        "failed",
                        input_count=validated.input_count if validated else 0,
                        output_count=validated.output_count if validated else 0,
                        valid_count=validated.valid_count if validated else 0,
                        missing_count=validated.missing_count if validated else 0,
                        invalid_count=validated.invalid_count if validated else 0,
                        duration_ms=self.item_durations.get(version_id, 0),
                        quality_summary=validated.quality_summary() if validated else {},
                        error_code=error_code,
                        error_message=message,
                    )
                    self.item_states[version_id] = "failed"
                    terminal_status = "failed"
                if terminal_status:
                    record_feature_item(
                        self._feature_code(version_id),
                        terminal_status,
                        self.item_durations.get(version_id, 0),
                        self.results[version_id].coverage_ratio if version_id in self.results else 0.0,
                    )
            except Exception as cleanup_exc:
                if ctx.logger:
                    ctx.logger.warning(
                        {
                            "event": "feature_item_cleanup_failed",
                            "run_id": self.payload.run_id,
                            "feature_version_id": version_id,
                            "error": str(cleanup_exc),
                        }
                    )
        try:
            detail = self.client.get_run(self.payload.run_id, include_subjects=False)
            status = str((detail.get("run") or {}).get("status", self.remote_status))
            if status == "queued":
                self.client.cancel_run(self.payload.run_id)
            elif status in {"planning", "running", "validating"}:
                self.client.fail_run(self.payload.run_id, error_code, message)
        except Exception as cleanup_exc:
            if ctx.logger:
                ctx.logger.warning(
                    {
                        "event": "feature_run_cleanup_failed",
                        "run_id": self.payload.run_id,
                        "error": str(cleanup_exc),
                    }
                )
        if self.plan:
            for version_id in self.plan.root_version_ids:
                record_feature_run(self._feature_code(version_id), "failed")
        if ctx.logger:
            ctx.logger.error(
                {
                    "event": "feature_run_failed",
                    "run_id": self.payload.run_id,
                    "feature_version_id": self.current_feature_version_id,
                    "producer_service": "artemis",
                    "source_profile": self.payload.source_profile,
                    "as_of_time": self.payload.as_of_time.isoformat(),
                    "data_cutoff_time": self.payload.data_cutoff_time.isoformat(),
                    "phase": ctx.failed_phase or "unknown",
                    "status": "failed",
                    "error_code": error_code,
                    "error": message,
                }
            )

    def run(self, ctx) -> None:
        try:
            super().run(ctx)
        except Exception as exc:
            self._cleanup_failed_run(ctx, exc)
            raise
        finally:
            self._stop_heartbeat()

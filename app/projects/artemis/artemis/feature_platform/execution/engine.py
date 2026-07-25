from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureNumericOutput
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.execution.output_validator import OutputValidator, ValidatedOutput
from artemis.feature_platform.execution.python_executor import PythonFeatureExecutor
from artemis.feature_platform.execution.runner import FeatureRunner
from artemis.feature_platform.manifests.checksum import manifest_registry_checksum
from artemis.feature_platform.manifests.loader import LoadedCatalog
from artemis.feature_platform.planning import ExecutionPlan
from artemis.feature_platform.planning.execution_plan import PlanNode
from artemis.feature_platform.providers.base import FeatureDataProvider


@dataclass(frozen=True)
class FeatureExecutionResult:
    validated: dict[int, ValidatedOutput]
    outputs: dict[int, FeatureNumericOutput]
    durations_ms: dict[int, int]


NodeStarted = Callable[[PlanNode], None]
NodeCompleted = Callable[[PlanNode, ValidatedOutput, int], None]


class FeatureExecutionEngine:
    """Shared plugin/DAG kernel used by persisted runs and in-memory previews."""

    def __init__(self, plugin_timeout_seconds: float) -> None:
        self.runner = FeatureRunner(
            PythonFeatureExecutor(plugin_timeout_seconds),
            OutputValidator(),
        )

    @staticmethod
    def validate_plan(
        plan: ExecutionPlan,
        catalog: LoadedCatalog,
    ) -> dict[int, bool]:
        requires_availability: dict[int, bool] = {}
        for node in plan.ordered_nodes:
            manifest = catalog.get(
                node.registry_version.feature_code,
                node.registry_version.version_number,
            )
            if manifest_registry_checksum(manifest) != node.registry_version.manifest_checksum:
                raise FeaturePlatformError(
                    "MANIFEST_CHECKSUM_CONFLICT",
                    f"local manifest {manifest.identity} differs from the published registry version",
                    status_code=409,
                )
            upstream_requires = any(
                requires_availability.get(upstream_id, False)
                for upstream_id in node.feature_dependency_ids
            )
            requires_availability[node.id] = bool(node.data_field_dependencies) or upstream_requires
        return requires_availability

    def execute(
        self,
        *,
        execution_id: str,
        plan: ExecutionPlan,
        catalog: LoadedCatalog,
        provider: FeatureDataProvider,
        security_ids: tuple[int, ...],
        as_of_time: datetime,
        data_cutoff_time: datetime,
        source_profile: str,
        market: str,
        implementation_overrides: dict[int, dict[str, object]] | None = None,
        requires_availability: dict[int, bool] | None = None,
        on_node_started: NodeStarted | None = None,
        on_node_completed: NodeCompleted | None = None,
    ) -> FeatureExecutionResult:
        availability = requires_availability or self.validate_plan(plan, catalog)
        validated_by_id: dict[int, ValidatedOutput] = {}
        outputs: dict[int, FeatureNumericOutput] = {}
        durations: dict[int, int] = {}
        overrides = implementation_overrides or {}

        for node in plan.ordered_nodes:
            if on_node_started:
                on_node_started(node)
            manifest = catalog.get(
                node.registry_version.feature_code,
                node.registry_version.version_number,
            )
            dependency_outputs = {
                upstream_id: outputs[upstream_id]
                for upstream_id in node.feature_dependency_ids
            }
            context = FeatureExecutionContext(
                run_id=execution_id,
                node=node,
                manifest=manifest,
                as_of_time=as_of_time,
                data_cutoff_time=data_cutoff_time,
                security_ids=security_ids,
                source_profile=source_profile,
                market=market,
                parameters={},
                implementation_overrides=dict(overrides.get(node.id, {})),
                dependency_outputs=dependency_outputs,
            )
            started = time.monotonic()
            validated = self.runner.compute(
                context,
                provider,
                requires_source_availability=availability[node.id],
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            validated_by_id[node.id] = validated
            outputs[node.id] = validated.output
            durations[node.id] = duration_ms
            if on_node_completed:
                on_node_completed(node, validated, duration_ms)

        return FeatureExecutionResult(
            validated=validated_by_id,
            outputs=outputs,
            durations_ms=durations,
        )

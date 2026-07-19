from __future__ import annotations

import queue
import threading
from typing import Any

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureNumericOutput
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.manifests.validator import load_entrypoint
from artemis.feature_platform.providers.base import FeatureDataProvider


class PythonFeatureExecutor:
    def __init__(self, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _invoke(
        plugin_class: type[Any],
        ctx: FeatureExecutionContext,
        provider: FeatureDataProvider,
    ) -> FeatureNumericOutput:
        try:
            plugin = plugin_class()
        except Exception as exc:
            raise FeaturePlatformError(
                "PLUGIN_INITIALIZATION_FAILED",
                f"cannot initialize {ctx.manifest.implementation.entrypoint}: {exc}",
            ) from exc
        registry = ctx.node.registry_version
        plugin.validate(registry.definition, registry.version, registry.implementation)
        dependencies = [
            registry.dependency_snapshot(dependency)
            for dependency in registry.dependencies
        ]
        inputs = plugin.load_inputs(ctx, provider, dependencies)
        output = plugin.compute(ctx, inputs)
        if not isinstance(output, FeatureNumericOutput):
            try:
                output = FeatureNumericOutput.model_validate(output)
            except Exception as exc:
                raise FeaturePlatformError(
                    "OUTPUT_SCHEMA_INVALID",
                    f"plugin {ctx.feature_code} returned an invalid output: {exc}",
                ) from exc
        plugin.validate_output(ctx, output)
        return output

    def execute(
        self,
        ctx: FeatureExecutionContext,
        provider: FeatureDataProvider,
    ) -> FeatureNumericOutput:
        plugin_class = load_entrypoint(ctx.manifest.implementation.entrypoint)
        result: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

        def invoke() -> None:
            try:
                result.put((True, self._invoke(plugin_class, ctx, provider)), block=False)
            except BaseException as exc:  # contain plugin SystemExit/KeyboardInterrupt in its worker
                result.put((False, exc), block=False)

        worker = threading.Thread(
            target=invoke,
            name=f"feature-{ctx.feature_version_id}",
            daemon=True,
        )
        worker.start()
        worker.join(self.timeout_seconds)
        if worker.is_alive():
            raise FeaturePlatformError(
                "PLUGIN_TIMEOUT",
                (
                    f"plugin {ctx.feature_code}@{ctx.manifest.version.number} exceeded "
                    f"{self.timeout_seconds:g}s timeout"
                ),
            )
        succeeded, payload = result.get_nowait()
        if succeeded:
            return payload
        if isinstance(payload, FeaturePlatformError):
            raise payload
        if isinstance(payload, Exception):
            raise FeaturePlatformError(
                "PLUGIN_EXECUTION_FAILED",
                f"plugin {ctx.feature_code}@{ctx.manifest.version.number} failed: {payload}",
            ) from payload
        raise FeaturePlatformError(
            "PLUGIN_EXECUTION_FAILED",
            f"plugin {ctx.feature_code}@{ctx.manifest.version.number} terminated with {type(payload).__name__}",
        )

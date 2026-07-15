from __future__ import annotations

from typing import Any, Protocol

from artemis.feature_platform.domain.models import FeatureNumericOutput
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.providers.base import FeatureDataProvider


class FeaturePlugin(Protocol):
    def validate(self, definition: dict, version: dict, implementation: dict) -> None:
        ...

    def load_inputs(
        self,
        ctx: FeatureExecutionContext,
        provider: FeatureDataProvider,
        dependencies: list[dict],
    ) -> Any:
        ...

    def compute(self, ctx: FeatureExecutionContext, inputs: Any) -> FeatureNumericOutput:
        ...

    def validate_output(self, ctx: FeatureExecutionContext, output: FeatureNumericOutput) -> None:
        ...

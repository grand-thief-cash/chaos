from __future__ import annotations

from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.execution.output_validator import OutputValidator, ValidatedOutput
from artemis.feature_platform.execution.python_executor import PythonFeatureExecutor
from artemis.feature_platform.providers.base import FeatureDataProvider


class FeatureRunner:
    def __init__(self, executor: PythonFeatureExecutor, validator: OutputValidator) -> None:
        self.executor = executor
        self.validator = validator

    def compute(
        self,
        ctx: FeatureExecutionContext,
        provider: FeatureDataProvider,
        *,
        requires_source_availability: bool,
    ) -> ValidatedOutput:
        output = self.executor.execute(ctx, provider)
        return self.validator.validate(
            ctx,
            output,
            requires_source_availability=requires_source_availability,
        )

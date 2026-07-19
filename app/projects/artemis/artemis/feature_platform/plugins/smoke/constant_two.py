from __future__ import annotations

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureNumericOutput, NumericValue
from artemis.feature_platform.execution.context import FeatureExecutionContext


class ConstantTwoFeature:
    """Phase 5 version-coexistence probe with no research meaning."""

    def validate(self, definition: dict, version: dict, implementation: dict) -> None:
        if definition.get("value_type") != "number":
            raise FeaturePlatformError("INPUT_SCHEMA_INVALID", "constant_two requires number value_type")

    def load_inputs(self, ctx: FeatureExecutionContext, provider, dependencies: list[dict]):
        if dependencies:
            raise FeaturePlatformError("DEPENDENCY_REFERENCE_INVALID", "constant_two must not have dependencies")
        return None

    def compute(self, ctx: FeatureExecutionContext, inputs) -> FeatureNumericOutput:
        return FeatureNumericOutput(
            feature_version_id=ctx.feature_version_id,
            observed_at=ctx.as_of_time,
            rows=[
                NumericValue(
                    security_id=security_id,
                    value=2.0,
                    value_status="valid",
                    quality_flags={"smoke": "constant_two"},
                )
                for security_id in ctx.security_ids
            ],
        )

    def validate_output(self, ctx: FeatureExecutionContext, output: FeatureNumericOutput) -> None:
        if len(output.rows) != len(ctx.security_ids):
            raise FeaturePlatformError("OUTPUT_SCHEMA_INVALID", "constant_two must output every subject")

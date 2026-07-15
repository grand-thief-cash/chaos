from __future__ import annotations

import math
from dataclasses import dataclass

from artemis.feature_platform.domain.enums import ValueStatus, ValueType
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureNumericOutput
from artemis.feature_platform.execution.context import FeatureExecutionContext


@dataclass(frozen=True)
class ValidatedOutput:
    output: FeatureNumericOutput
    input_count: int
    output_count: int
    valid_count: int
    missing_count: int
    invalid_count: int
    coverage_ratio: float

    def quality_summary(self) -> dict:
        return {
            "coverage_ratio": self.coverage_ratio,
            "valid_count": self.valid_count,
            "missing_count": self.missing_count,
            "invalid_count": self.invalid_count,
        }


class OutputValidator:
    def validate(
        self,
        ctx: FeatureExecutionContext,
        output: FeatureNumericOutput,
        *,
        requires_source_availability: bool,
    ) -> ValidatedOutput:
        if output.feature_version_id != ctx.feature_version_id:
            raise FeaturePlatformError(
                "OUTPUT_SCHEMA_INVALID",
                f"plugin output version {output.feature_version_id} does not match {ctx.feature_version_id}",
            )
        if output.observed_at != ctx.as_of_time:
            raise FeaturePlatformError(
                "OUTPUT_SCHEMA_INVALID",
                "Phase 2 output observed_at must equal run as_of_time",
            )

        universe = set(ctx.security_ids)
        seen: set[int] = set()
        valid_count = missing_count = invalid_count = 0
        for row in output.rows:
            if row.security_id in seen:
                raise FeaturePlatformError(
                    "OUTPUT_DUPLICATE_SUBJECT",
                    f"plugin output duplicated security_id {row.security_id}",
                )
            seen.add(row.security_id)
            if row.security_id not in universe:
                raise FeaturePlatformError(
                    "OUTPUT_OUTSIDE_UNIVERSE",
                    f"plugin output security_id {row.security_id} is outside the frozen universe",
                )
            if row.value_status == ValueStatus.VALID:
                numeric = float(row.value)  # type narrowing is enforced by NumericValue
                if not math.isfinite(numeric):
                    raise FeaturePlatformError(
                        "OUTPUT_NAN_OR_INFINITE",
                        f"plugin output for security_id {row.security_id} is not finite",
                    )
                if ctx.manifest.feature.value_type == ValueType.INTEGER and not numeric.is_integer():
                    raise FeaturePlatformError(
                        "OUTPUT_SCHEMA_INVALID",
                        f"integer feature returned a non-integer value for security_id {row.security_id}",
                    )
                valid_count += 1
            elif row.value_status == ValueStatus.MISSING:
                missing_count += 1
            else:
                invalid_count += 1
            if row.source_max_available_at is not None and row.source_max_available_at > ctx.data_cutoff_time:
                raise FeaturePlatformError(
                    "DATA_CUTOFF_VIOLATION",
                    f"plugin output for security_id {row.security_id} exceeds data_cutoff_time",
                )
            if requires_source_availability and row.source_max_available_at is None:
                raise FeaturePlatformError(
                    "SOURCE_AVAILABILITY_REQUIRED",
                    f"plugin output for security_id {row.security_id} lacks source availability",
                )

        coverage = valid_count / len(universe) if universe else 0.0
        if coverage < ctx.manifest.quality.min_coverage_ratio:
            raise FeaturePlatformError(
                "QUALITY_GATE_FAILED",
                (
                    f"feature {ctx.feature_code} coverage {coverage:.6f} is below "
                    f"{ctx.manifest.quality.min_coverage_ratio:.6f}"
                ),
            )
        return ValidatedOutput(
            output=output,
            input_count=len(universe),
            output_count=len(output.rows),
            valid_count=valid_count,
            missing_count=missing_count,
            invalid_count=invalid_count,
            coverage_ratio=coverage,
        )

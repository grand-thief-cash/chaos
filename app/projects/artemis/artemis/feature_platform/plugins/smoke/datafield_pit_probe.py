from __future__ import annotations

import math

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureNumericOutput, NumericValue
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.providers.base import DataFieldBatch


class DataFieldPITProbeFeature:
    """PIT plumbing probe. It is intentionally not a financial business factor."""

    def validate(self, definition: dict, version: dict, implementation: dict) -> None:
        if definition.get("value_type") != "number":
            raise FeaturePlatformError("INPUT_SCHEMA_INVALID", "PIT probe requires number value_type")

    def load_inputs(self, ctx: FeatureExecutionContext, provider, dependencies: list[dict]) -> DataFieldBatch:
        data_fields = [item for item in dependencies if item.get("kind") == "data_field"]
        if len(data_fields) != 1 or len(dependencies) != 1:
            raise FeaturePlatformError(
                "DEPENDENCY_REFERENCE_INVALID",
                "PIT probe requires exactly one governed data_field dependency",
            )
        return provider.load_data_field(ctx, data_fields[0])

    def compute(self, ctx: FeatureExecutionContext, inputs: DataFieldBatch) -> FeatureNumericOutput:
        by_security: dict[int, list] = {security_id: [] for security_id in ctx.security_ids}
        for record in inputs.records:
            by_security[record.security_id].append(record)

        rows: list[NumericValue] = []
        for security_id in ctx.security_ids:
            candidates = by_security[security_id]
            if not candidates:
                # PhoenixA Phase 1 requires an availability bound even for an
                # explicit missing row. The cutoff is the negative-query bound,
                # while quality_flags makes clear that no source record was used.
                rows.append(
                    NumericValue(
                        security_id=security_id,
                        value=None,
                        value_status="missing",
                        quality_flags={
                            "reason": "no_source_record_at_cutoff",
                            "availability_bound": "data_cutoff_time",
                        },
                        source_max_available_at=ctx.data_cutoff_time,
                    )
                )
                continue
            selected = max(
                candidates,
                key=lambda item: (
                    item.available_at,
                    item.reporting_period,
                    str(item.metadata.get("statement_code") or ""),
                    str(item.metadata.get("report_type") or ""),
                ),
            )
            try:
                value = float(selected.value)
            except (TypeError, ValueError):
                value = math.nan
            if not math.isfinite(value):
                rows.append(
                    NumericValue(
                        security_id=security_id,
                        value=None,
                        value_status="invalid",
                        quality_flags={"reason": "source_value_not_finite"},
                        source_max_available_at=selected.available_at,
                    )
                )
            else:
                rows.append(
                    NumericValue(
                        security_id=security_id,
                        value=value,
                        value_status="valid",
                        quality_flags={
                            "smoke": "datafield_pit_probe",
                            "reporting_period": selected.reporting_period,
                        },
                        source_max_available_at=selected.available_at,
                    )
                )
        return FeatureNumericOutput(
            feature_version_id=ctx.feature_version_id,
            observed_at=ctx.as_of_time,
            rows=rows,
        )

    def validate_output(self, ctx: FeatureExecutionContext, output: FeatureNumericOutput) -> None:
        if len(output.rows) != len(ctx.security_ids):
            raise FeaturePlatformError("OUTPUT_SCHEMA_INVALID", "PIT probe must output every subject")

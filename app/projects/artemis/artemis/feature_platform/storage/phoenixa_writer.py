from __future__ import annotations

from artemis.feature_platform.execution.output_validator import ValidatedOutput
from artemis.feature_platform.registry.client import FeatureRegistryClient


class PhoenixAFeatureWriter:
    def __init__(self, client: FeatureRegistryClient, batch_size: int = 5000) -> None:
        if batch_size <= 0 or batch_size > 5000:
            raise ValueError("batch_size must be between 1 and 5000")
        self.client = client
        self.batch_size = batch_size

    def write(self, run_id: str, validated: ValidatedOutput) -> int:
        output = validated.output
        written = 0
        for start in range(0, len(output.rows), self.batch_size):
            rows = output.rows[start : start + self.batch_size]
            payload = [row.model_dump(mode="json") for row in rows]
            self.client.write_numeric_values(
                run_id,
                output.feature_version_id,
                output.observed_at,
                payload,
            )
            written += len(rows)
        return written

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from artemis.feature_platform.execution.context import FeatureExecutionContext


@dataclass(frozen=True)
class DataFieldRecord:
    security_id: int
    value: Any
    available_at: datetime
    reporting_period: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DataFieldBatch:
    dependency: dict[str, Any]
    records: tuple[DataFieldRecord, ...]


class FeatureDataProvider(Protocol):
    def load_data_field(self, ctx: FeatureExecutionContext, dependency: dict[str, Any]) -> DataFieldBatch:
        ...

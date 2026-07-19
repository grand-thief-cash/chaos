from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from artemis.feature_platform.domain.models import FeatureManifest, FeatureNumericOutput
from artemis.feature_platform.planning.execution_plan import PlanNode


@dataclass(frozen=True)
class FeatureExecutionContext:
    run_id: str
    node: PlanNode
    manifest: FeatureManifest
    as_of_time: datetime
    data_cutoff_time: datetime
    security_ids: tuple[int, ...]
    source_profile: str
    market: str
    parameters: dict[str, Any] = field(default_factory=dict)
    dependency_outputs: dict[int, FeatureNumericOutput] = field(default_factory=dict)

    @property
    def feature_version_id(self) -> int:
        return self.node.id

    @property
    def feature_code(self) -> str:
        return self.node.registry_version.feature_code

    @property
    def implementation_config(self) -> dict[str, Any]:
        return dict(self.manifest.implementation.config)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Type

import backtrader as bt

from artemis.backtrader.strategies.registry_map import STRATEGY_REGISTRY_MAP


@dataclass(frozen=True)
class StrategySpec:
    code: str
    cls: Type[bt.Strategy]
    default_params: Dict[str, Any] = field(default_factory=dict)
    supported_modes: tuple[str, ...] = ("historical",)
    supported_timeframes: tuple[str, ...] = ("daily",)


class StrategyRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, StrategySpec] = {}

    def register(self, spec: StrategySpec) -> None:
        self._registry[spec.code] = spec

    def get(self, code: str) -> StrategySpec | None:
        return self._registry.get(str(code).strip())

    def require(self, code: str) -> StrategySpec:
        spec = self.get(code)
        if not spec:
            raise ValueError(f"strategy_code '{code}' is not registered")
        return spec

    def has(self, code: str) -> bool:
        return self.get(code) is not None


strategy_registry = StrategyRegistry()
for registration in STRATEGY_REGISTRY_MAP:
    strategy_registry.register(
        StrategySpec(
            code=registration.code,
            cls=registration.cls,
            default_params=dict(registration.default_params),
            supported_modes=tuple(registration.supported_modes),
            supported_timeframes=tuple(registration.supported_timeframes),
        )
    )


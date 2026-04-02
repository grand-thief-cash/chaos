from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Type

import backtrader as bt

from artemis.strategy_engine.strategies.registry_map import STRATEGY_REGISTRY_MAP


@dataclass(frozen=True)
class StrategySpec:
    """策略规格，定义策略类、默认参数、支持的回测模式和参数校验规则。"""
    code: str
    cls: Type[bt.Strategy]
    default_params: Dict[str, Any] = field(default_factory=dict)
    supported_modes: tuple[str, ...] = ("historical",)
    supported_timeframes: tuple[str, ...] = ("daily",)
    param_schema: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """根据 param_schema 校验策略参数，返回错误信息列表。"""
        """Validate strategy params against schema. Returns list of error messages."""
        errors: List[str] = []
        for key, rule in self.param_schema.items():
            value = params.get(key)
            if rule.get("required") and value is None:
                errors.append(f"strategy_params.{key} is required")
                continue
            if value is None:
                continue
            if rule.get("type") == "int":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    errors.append(f"strategy_params.{key} must be int")
                    continue
                min_val = rule.get("min")
                if min_val is not None and value < min_val:
                    errors.append(f"strategy_params.{key} must be >= {min_val}")
        return errors


class StrategyRegistry:
    """策略注册表，管理所有可用的策略规格，支持注册、查询和参数校验。"""
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
            param_schema=dict(registration.param_schema),
        )
    )


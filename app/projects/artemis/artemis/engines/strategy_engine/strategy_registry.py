from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Type

import backtrader as bt


@dataclass(frozen=True)
class StrategySpec:
    """策略规格，定义策略类、默认参数、支持的回测模式和参数校验规则。"""
    code: str
    cls: Type[bt.Strategy]
    default_params: Dict[str, Any] = field(default_factory=dict)
    supported_modes: tuple[str, ...] = ("historical",)
    supported_timeframes: tuple[str, ...] = ("daily",)
    param_schema: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    version: str = "v1"

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """根据 param_schema 校验策略参数，返回错误信息列表。

        支持的 schema rule 字段：
          - type: "int" | "float" | "str" | "enum"
          - required: bool
          - min: number（适用于 int / float）
          - max: number（适用于 int / float）
          - options: list（适用于 enum）
          - default: Any（仅供前端表单使用，校验时不回填）
          - description: str（参数说明，仅供展示）
          - display_name: str（参数显示名，仅供展示）
        """
        errors: List[str] = []
        for key, rule in self.param_schema.items():
            value = params.get(key)

            # required 检查
            if rule.get("required") and value is None:
                errors.append(f"strategy_params.{key} is required")
                continue
            if value is None:
                continue

            param_type = rule.get("type", "")

            # ── int 类型 ───────────────────────────────────────
            if param_type == "int":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    errors.append(f"strategy_params.{key} must be int")
                    continue
                min_val = rule.get("min")
                if min_val is not None and value < min_val:
                    errors.append(f"strategy_params.{key} must be >= {min_val}")
                max_val = rule.get("max")
                if max_val is not None and value > max_val:
                    errors.append(f"strategy_params.{key} must be <= {max_val}")

            # ── float 类型 ─────────────────────────────────────
            elif param_type == "float":
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    errors.append(f"strategy_params.{key} must be float")
                    continue
                min_val = rule.get("min")
                if min_val is not None and value < min_val:
                    errors.append(f"strategy_params.{key} must be >= {min_val}")
                max_val = rule.get("max")
                if max_val is not None and value > max_val:
                    errors.append(f"strategy_params.{key} must be <= {max_val}")

            # ── str 类型 ───────────────────────────────────────
            elif param_type == "str":
                if not isinstance(value, str):
                    errors.append(f"strategy_params.{key} must be str")

            # ── enum 类型 ──────────────────────────────────────
            elif param_type == "enum":
                options = rule.get("options", [])
                if value not in options:
                    errors.append(f"strategy_params.{key} must be one of {options}")

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


def _build_registry() -> StrategyRegistry:
    """构建策略注册表：优先使用 @register_strategy 装饰器收集的策略，
    同时兼容 registry_map.py 中的手动注册条目。

    装饰器注册的策略如果与 registry_map 中的条目 code 冲突，装饰器优先。
    """
    registry = StrategyRegistry()

    # 1. 加载 registry_map（向后兼容，逐步迁移到装饰器后可移除）
    from artemis.engines.strategy_engine.strategies.registry_map import STRATEGY_REGISTRY_MAP
    for registration in STRATEGY_REGISTRY_MAP:
        registry.register(
            StrategySpec(
                code=registration.code,
                cls=registration.cls,
                default_params=dict(registration.default_params),
                supported_modes=tuple(registration.supported_modes),
                supported_timeframes=tuple(registration.supported_timeframes),
                param_schema=dict(registration.param_schema),
            )
        )

    # 2. 加载 @register_strategy 装饰器收集的策略（优先级高于 registry_map）
    from artemis.engines.strategy_engine.strategies.base import _PENDING_REGISTRATIONS
    for reg in _PENDING_REGISTRATIONS:
        registry.register(
            StrategySpec(
                code=reg["code"],
                cls=reg["cls"],
                default_params=dict(reg["default_params"]),
                supported_modes=tuple(reg["supported_modes"]),
                supported_timeframes=tuple(reg["supported_timeframes"]),
                param_schema=dict(reg["param_schema"]),
            )
        )

    return registry


strategy_registry = _build_registry()


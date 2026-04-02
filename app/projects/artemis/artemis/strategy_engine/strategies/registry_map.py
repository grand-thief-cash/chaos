from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import backtrader as bt

from artemis.strategy_engine.strategies.sma_cross import SmaCrossStrategy


@dataclass(frozen=True)
class StrategyRegistration:
    """策略注册条目，包含策略代码、类、默认参数、支持的模式和参数校验规则。"""
    code: str
    cls: type[bt.Strategy]
    default_params: dict[str, Any] = field(default_factory=dict)
    supported_modes: tuple[str, ...] = ("historical",)
    supported_timeframes: tuple[str, ...] = ("daily",)
    param_schema: dict[str, dict[str, Any]] = field(default_factory=dict)


# 策略注册映射表，Phase 1 阶段手动维护。
# 新增策略时在此添加 StrategyRegistration 条目即可。
STRATEGY_REGISTRY_MAP: tuple[StrategyRegistration, ...] = (
    StrategyRegistration(
        code="sma_cross",
        cls=SmaCrossStrategy,
        default_params={"fast": 10, "slow": 30, "stake": 1},
        supported_modes=("historical",),
        supported_timeframes=("daily",),
        param_schema={
            "fast": {"type": "int", "min": 1},
            "slow": {"type": "int", "min": 1},
            "stake": {"type": "int", "min": 1},
        },
    ),
)


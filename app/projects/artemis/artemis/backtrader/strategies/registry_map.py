from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import backtrader as bt

from artemis.backtrader.strategies.sma_cross import SmaCrossStrategy


@dataclass(frozen=True)
class StrategyRegistration:
    code: str
    cls: type[bt.Strategy]
    default_params: dict[str, Any] = field(default_factory=dict)
    supported_modes: tuple[str, ...] = ("historical",)
    supported_timeframes: tuple[str, ...] = ("daily",)


STRATEGY_REGISTRY_MAP: tuple[StrategyRegistration, ...] = (
    StrategyRegistration(
        code="sma_cross",
        cls=SmaCrossStrategy,
        default_params={"fast": 10, "slow": 30, "stake": 1},
        supported_modes=("historical",),
        supported_timeframes=("daily",),
    ),
)


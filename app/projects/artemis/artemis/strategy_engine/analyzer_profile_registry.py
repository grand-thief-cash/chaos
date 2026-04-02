from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

import backtrader as bt


@dataclass(frozen=True)
class AnalyzerProfileSpec:
    """分析器配置规格，定义回测中使用的分析器和观察器组合。"""
    code: str
    supported_modes: tuple[str, ...] = ("historical",)
    supported_timeframes: tuple[str, ...] = ("daily",)
    analyzers: Tuple[Tuple[str, type[Any], Dict[str, Any]], ...] = field(default_factory=tuple)
    observers: Tuple[Tuple[str, type[Any], Dict[str, Any]], ...] = field(default_factory=tuple)
    persist_artifacts: tuple[str, ...] = (
        "analyzers",
        "trades",
        "equity_curve",
        "plot_manifest",
        "plot_series",
    )


class AnalyzerProfileRegistry:
    """分析器配置注册表，管理所有可用的分析器配置规格。"""

    def __init__(self) -> None:
        self._registry: Dict[str, AnalyzerProfileSpec] = {}

    def register(self, spec: AnalyzerProfileSpec) -> None:
        self._registry[spec.code] = spec

    def get(self, code: str) -> AnalyzerProfileSpec | None:
        return self._registry.get(str(code).strip())

    def require(self, code: str) -> AnalyzerProfileSpec:
        spec = self.get(code)
        if not spec:
            raise ValueError(f"analyzer_profile '{code}' is not registered")
        return spec


default_hist_profile = AnalyzerProfileSpec(
    code="default_hist_v1",
    analyzers=(
        ("returns", bt.analyzers.Returns, {}),
        ("drawdown", bt.analyzers.DrawDown, {}),
        ("trade_analyzer", bt.analyzers.TradeAnalyzer, {}),
        ("sharpe", bt.analyzers.SharpeRatio_A, {"riskfreerate": 0.0}),
    ),
    observers=(
        ("broker", bt.observers.Broker, {}),
    ),
)

analyzer_profile_registry = AnalyzerProfileRegistry()
analyzer_profile_registry.register(default_hist_profile)


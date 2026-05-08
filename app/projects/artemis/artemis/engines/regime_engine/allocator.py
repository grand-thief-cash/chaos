"""策略分配器 — 从连续状态向量映射到策略权重。"""

from __future__ import annotations

from typing import Dict

from artemis.engines.regime_engine.models import RegimeState, StrategyAllocation


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class StrategyAllocator:
    """连续亲和力函数：state → strategy weights。"""

    def allocate(self, state: RegimeState) -> StrategyAllocation:
        t = state.trend_strength
        b = state.market_breadth
        v = state.volatility_stress
        l = state.liquidity
        c = state.sector_concentration
        r = state.risk_appetite

        momentum_w = t * 0.4 + b * 0.3 + (1 - v) * 0.2 + l * 0.1
        trend_neutrality = 1.0 - abs(t - 0.5) * 2
        mean_rev_w = trend_neutrality * 0.5 + v * 0.2 + (1 - c) * 0.3
        factor_w = b * 0.3 + (1 - v) * 0.3 + 0.4
        event_w = c * 0.4 + r * 0.3 + l * 0.3

        total = momentum_w + mean_rev_w + factor_w + event_w
        if total < 1e-8:
            total = 1.0

        weights = {
            "momentum": momentum_w / total,
            "mean_reversion": mean_rev_w / total,
            "factor_select": factor_w / total,
            "event_driven": event_w / total,
        }

        pos = self._position_limit(state)
        hp = "short" if v > 0.7 else ("medium" if (t > 0.7 or t < 0.3) else "short")

        factor_adj = FactorWeightAdjuster.adjust(state)

        return StrategyAllocation(
            weights=weights,
            factor_weight_adjustments=factor_adj,
            position_limit=pos,
            suggested_holding_period=hp,
        )

    @staticmethod
    def _position_limit(state: RegimeState) -> float:
        penalty = (
            state.volatility_stress * 0.6
            + max(0.0, -state.breadth_momentum) * 0.3
            + max(0.0, 0.3 - state.trend_strength) * 0.5
        )
        return _clip(0.9 - penalty, 0.05, 1.0)


class FactorWeightAdjuster:
    """因子权重连续调整。"""

    @staticmethod
    def adjust(state: RegimeState) -> Dict[str, float]:
        t = state.trend_strength
        v = state.volatility_stress
        r = state.risk_appetite
        return {
            "growth_revenue_yoy": 1.0 + (t - 0.5) * 1.0 + (r - 0.5) * 0.5,
            "quality_cash_conversion": 1.0 + v * 0.8,
            "profitability_roe": 1.0 + (t - 0.5) * 0.3,
            "valuation_pe_ttm": 1.0 + (0.5 - t) * 0.8 + v * 0.3,
            "per_share_dps": 1.0 + (0.5 - r) * 1.2 + v * 0.5,
            "solvency_debt_ratio": 1.0 + v * 0.6,
        }


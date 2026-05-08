"""Regime Engine 数据模型 — 连续状态空间。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RegimeFeatures:
    """MVP 特征向量 — 8 个核心特征。"""
    trade_date: str = ""

    # 趋势
    hs300_distance_from_ma120: float = 0.0   # (close - ma120) / ma120
    hs300_ma20_slope: float = 0.0            # MA20 5日变化率

    # 广度
    breadth_above_ma20_pct: float = 0.5      # 全市场站上MA20占比

    # 波动率
    vol_20d: float = 0.15                    # 20日年化波动率
    vol_ratio: float = 1.0                   # vol_20d / vol_60d

    # 流动性
    turnover_ratio: float = 1.0              # 今日成交额 / 20日均值

    # 风格
    style_small_vs_large: float = 0.0        # 中证1000 20d收益 - 沪深300 20d收益

    # 行业集中度
    industry_concentration: float = 0.0       # HHI 变体


@dataclass
class RegimeState:
    """6+2 维连续状态向量。"""
    trade_date: str = ""

    # 核心维度 (0.0‑1.0)
    trend_strength: float = 0.5              # 0=强空头, 0.5=无趋势, 1=强多头
    risk_appetite: float = 0.5               # 0=极度避险, 1=极度冒险
    volatility_stress: float = 0.3           # 0=平静, 1=极端波动
    market_breadth: float = 0.5              # 0=全面下跌, 1=全面上涨
    liquidity: float = 0.5                   # 0=枯竭, 1=泛滥
    sector_concentration: float = 0.2         # 0=均匀, 1=极端集中

    # 转换信号 (-1.0 ~ +1.0)
    breadth_momentum: float = 0.0            # 广度变化速度
    vol_acceleration: float = 0.0            # 波动率变化加速度

    # 便利标签 (策略不消费)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_state_vector(self) -> Dict[str, float]:
        return {
            "trend_strength": self.trend_strength,
            "risk_appetite": self.risk_appetite,
            "volatility_stress": self.volatility_stress,
            "market_breadth": self.market_breadth,
            "liquidity": self.liquidity,
            "sector_concentration": self.sector_concentration,
            "breadth_momentum": self.breadth_momentum,
            "vol_acceleration": self.vol_acceleration,
        }

    def to_dict(self) -> dict:
        d = self.to_state_vector()
        d["trade_date"] = self.trade_date
        d.update(self.labels)
        return d


@dataclass
class StrategyAllocation:
    """策略分配结果。"""
    weights: Dict[str, float] = field(default_factory=dict)
    factor_weight_adjustments: Dict[str, float] = field(default_factory=dict)
    position_limit: float = 0.9
    suggested_holding_period: str = "medium"

    def to_dict(self) -> dict:
        return {
            "strategy_weights": self.weights,
            "factor_weight_adjustments": self.factor_weight_adjustments,
            "position_limit": self.position_limit,
            "suggested_holding_period": self.suggested_holding_period,
        }


# ---------------------------------------------------------------------------
# Label derivation
# ---------------------------------------------------------------------------

def derive_labels(state: RegimeState) -> Dict[str, str]:
    """从连续状态向量推导离散标签（仅供人类/日志）。"""
    if state.volatility_stress > 0.8:
        lm = "PANIC"
    elif state.trend_strength > 0.65:
        lm = "BULL_TREND"
    elif state.trend_strength < 0.35:
        lm = "BEAR_TREND"
    else:
        lm = "SIDEWAYS"

    if state.volatility_stress > 0.75:
        lv = "SPIKE" if state.vol_acceleration > 0.3 else "HIGH"
    elif state.volatility_stress < 0.25:
        lv = "LOW"
    else:
        lv = "NORMAL"

    return {
        "label_market": lm,
        "label_vol": lv,
        "label_confidence": f"{abs(state.trend_strength - 0.5) * 2:.2f}",
    }


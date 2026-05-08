"""连续状态估计器 — 从特征向量映射到连续状态空间。"""

from __future__ import annotations

import math
from typing import Optional

from artemis.engines.regime_engine.config import RegimeConfig
from artemis.engines.regime_engine.models import RegimeFeatures, RegimeState, derive_labels


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _sigmoid_clip(x: float) -> float:
    """Map (-inf, +inf) to (-1, +1) without overflow."""
    clamped = max(-10.0, min(10.0, 3.0 * x))
    return 2.0 / (1.0 + math.exp(-clamped)) - 1.0


class RegimeStateEstimator:
    """连续状态估计器 — 无 if-else 阈值，EMA 平滑。"""

    def __init__(self, config: Optional[RegimeConfig] = None) -> None:
        self.config = config or RegimeConfig()
        self._prev: Optional[RegimeState] = None
        self._prev_features: Optional[RegimeFeatures] = None

    def reset(self) -> None:
        self._prev = None
        self._prev_features = None

    def estimate(self, features: RegimeFeatures) -> RegimeState:
        raw = RegimeState(
            trade_date=features.trade_date,
            trend_strength=self._trend(features),
            risk_appetite=self._risk(features),
            volatility_stress=self._vol_stress(features),
            market_breadth=_clip(features.breadth_above_ma20_pct),
            liquidity=_clip((features.turnover_ratio - 0.5) / 1.5),
            sector_concentration=_clip(features.industry_concentration),
            breadth_momentum=self._breadth_momentum(features),
            vol_acceleration=self._vol_acceleration(features),
        )

        if self._prev is not None:
            raw = self._ema_smooth(raw, self._prev)

        raw.labels = derive_labels(raw)

        self._prev = raw
        self._prev_features = features
        return raw

    # ------------------------------------------------------------------
    # Dimension computations
    # ------------------------------------------------------------------
    @staticmethod
    def _trend(f: RegimeFeatures) -> float:
        score = 0.5
        score += _sigmoid_clip(f.hs300_distance_from_ma120 / 0.15) * 0.4
        score += _clip(f.hs300_ma20_slope * 50, -0.1, 0.1)
        return _clip(score)

    @staticmethod
    def _risk(f: RegimeFeatures) -> float:
        base = _clip(f.breadth_above_ma20_pct)
        adj = _clip(f.style_small_vs_large / 0.10, -0.15, 0.15)
        return _clip(base + adj)

    @staticmethod
    def _vol_stress(f: RegimeFeatures) -> float:
        return _clip((f.vol_ratio - 0.7) / 1.3)

    def _breadth_momentum(self, f: RegimeFeatures) -> float:
        if self._prev_features is None:
            return 0.0
        delta = f.breadth_above_ma20_pct - self._prev_features.breadth_above_ma20_pct
        return _clip(delta / 0.20, -1.0, 1.0)

    def _vol_acceleration(self, f: RegimeFeatures) -> float:
        if self._prev_features is None:
            return 0.0
        prev_ratio = self._prev_features.vol_ratio
        if abs(prev_ratio) < 1e-8:
            return 0.0
        speed = (f.vol_ratio - prev_ratio) / prev_ratio
        return _clip(speed / 0.5, -1.0, 1.0)

    # ------------------------------------------------------------------
    # EMA smoothing
    # ------------------------------------------------------------------
    def _ema_smooth(self, raw: RegimeState, prev: RegimeState) -> RegimeState:
        a = self.config.smoothing_alpha
        smoothed = RegimeState(trade_date=raw.trade_date)

        for dim in ("trend_strength", "risk_appetite", "market_breadth",
                     "liquidity", "sector_concentration"):
            v = a * getattr(raw, dim) + (1 - a) * getattr(prev, dim)
            setattr(smoothed, dim, v)

        # vol_stress: 上行不平滑 (快速响应), 下行平滑
        if raw.volatility_stress > prev.volatility_stress:
            smoothed.volatility_stress = raw.volatility_stress
        else:
            smoothed.volatility_stress = a * raw.volatility_stress + (1 - a) * prev.volatility_stress

        # Transition signals 不平滑
        smoothed.breadth_momentum = raw.breadth_momentum
        smoothed.vol_acceleration = raw.vol_acceleration

        return smoothed


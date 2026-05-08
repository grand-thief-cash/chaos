"""Regime Engine 配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegimeConfig:
    """所有阈值集中管理。"""

    # 均线周期
    trend_ma_long: int = 120               # A 股用 120 (非美股 200)
    trend_ma_short: int = 20
    trend_ma_medium: int = 60

    # EMA 平滑
    smoothing_alpha: float = 0.3           # ≈ 5 天半衰期

    # 波动率
    vol_lookback_days: int = 500
    vol_20d_window: int = 20
    vol_60d_window: int = 60

    # 风格
    style_lookback_days: int = 20

    # 行业
    industry_count: int = 31               # 申万一级行业数


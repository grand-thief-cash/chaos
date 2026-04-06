"""指标注册表，声明式配置 ta 库指标映射。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

import pandas as pd
import numpy as np


@dataclass(frozen=True)
class IndicatorSpec:
    """指标规格定义。"""

    name: str  # 指标名，如 "sma"
    display_name: str  # 显示名，如 "SMA"
    default_params: Dict[str, Any]  # 默认参数
    overlay: bool  # 是否叠加到主图
    y_axis: str | None  # 子图 y 轴名（overlay=false 时有效）
    calculate: Callable[..., Dict[str, list]]  # 计算函数，接收 (df, **params) → {series_key: [values]}
    series_meta: Dict[str, Dict[str, Any]]  # 每个 series_key 的渲染元信息模板


def _safe_to_list(series: pd.Series) -> list:
    """将 pandas Series 转为 list，NaN/inf 统一替换为 None。"""
    import math
    result = []
    for v in series:
        if v is pd.NA or v is None:
            result.append(None)
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            result.append(None)
        elif isinstance(v, np.floating) and (np.isnan(v) or np.isinf(v)):
            result.append(None)
        else:
            result.append(v)
    return result


def _sma_calculate(df, *, period=10, **_kwargs):
    """SMA 简单移动平均线。"""
    values = df["close"].rolling(window=period).mean()
    key = f"sma_{period}"
    return {key: _safe_to_list(values.round(4))}


def _ema_calculate(df, *, period=10, **_kwargs):
    """EMA 指数移动平均线。"""
    from ta.trend import ema_indicator

    values = ema_indicator(df["close"], window=period)
    key = f"ema_{period}"
    return {key: _safe_to_list(values.round(4))}


def _rsi_calculate(df, *, period=14, **_kwargs):
    """RSI 相对强弱指数。"""
    from ta.momentum import rsi

    values = rsi(df["close"], window=period)
    key = f"rsi_{period}"
    return {key: _safe_to_list(values.round(4))}


def _macd_calculate(df, *, fast=12, slow=26, signal=9, **_kwargs):
    """MACD 异同移动平均线。"""
    from ta.trend import MACD

    macd = MACD(df["close"], window_fast=fast, window_slow=slow, window_sign=signal)
    suffix = f"{fast}_{slow}_{signal}"
    return {
        f"macd_{suffix}": _safe_to_list(macd.macd().round(4)),
        f"macd_signal_{suffix}": _safe_to_list(macd.macd_signal().round(4)),
        f"macd_hist_{suffix}": _safe_to_list(macd.macd_diff().round(4)),
    }


def _bbands_calculate(df, *, period=20, std_dev=2, **_kwargs):
    """Bollinger Bands 布林带。"""
    from ta.volatility import BollingerBands

    bb = BollingerBands(df["close"], window=period, window_dev=std_dev)
    suffix = f"{period}_{std_dev}"
    return {
        f"bb_upper_{suffix}": _safe_to_list(bb.bollinger_hband().round(4)),
        f"bb_middle_{suffix}": _safe_to_list(bb.bollinger_mavg().round(4)),
        f"bb_lower_{suffix}": _safe_to_list(bb.bollinger_lband().round(4)),
    }


def _kdj_calculate(df, *, k_period=14, k_smooth=3, d_smooth=3, **_kwargs):
    """KDJ 随机指标。"""
    from ta.momentum import StochasticOscillator

    stoch = StochasticOscillator(
        df["high"], df["low"], df["close"],
        window=k_period, smooth_window=k_smooth,
    )
    k = stoch.stoch()
    d = stoch.stoch_signal()
    j = 3 * k - 2 * d
    suffix = f"{k_period}_{k_smooth}_{d_smooth}"
    return {
        f"kdj_k_{suffix}": _safe_to_list(k.round(4)),
        f"kdj_d_{suffix}": _safe_to_list(d.round(4)),
        f"kdj_j_{suffix}": _safe_to_list(j.round(4)),
    }


def _skewness_calculate(df, *, period=20, **_kwargs):
    """Skewness 偏度 — 滚动窗口收益率的偏度。"""
    returns = df["close"].pct_change()
    values = returns.rolling(window=period).skew()
    key = f"skewness_{period}"
    return {key: _safe_to_list(values.round(4))}


def _kurtosis_calculate(df, *, period=20, **_kwargs):
    """Kurtosis 峰度 — 滚动窗口收益率的超额峰度。"""
    returns = df["close"].pct_change()
    values = returns.rolling(window=period).kurt()
    key = f"kurtosis_{period}"
    return {key: _safe_to_list(values.round(4))}


def _support_calculate(df, *, period=20, **_kwargs):
    """滚动支撑位 — 前 N 根 K 线（不含当前 bar）的最低价。"""
    values = df["low"].shift(1).rolling(window=period).min()
    key = f"support_{period}"
    return {key: _safe_to_list(values.round(4))}


def _breakout_calculate(df, *, period=20, **_kwargs):
    """滚动突破位 — 前 N 根 K 线（不含当前 bar）的最高价。"""
    values = df["high"].shift(1).rolling(window=period).max()
    key = f"breakout_{period}"
    return {key: _safe_to_list(values.round(4))}


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

INDICATOR_REGISTRY: Dict[str, IndicatorSpec] = {
    "sma": IndicatorSpec(
        name="sma",
        display_name="SMA",
        default_params={"period": 10},
        overlay=True,
        y_axis=None,
        calculate=_sma_calculate,
        series_meta={
            "sma_{period}": {"type": "line", "color": "#1890ff"},
        },
    ),
    "ema": IndicatorSpec(
        name="ema",
        display_name="EMA",
        default_params={"period": 10},
        overlay=True,
        y_axis=None,
        calculate=_ema_calculate,
        series_meta={
            "ema_{period}": {"type": "line", "color": "#faad14"},
        },
    ),
    "rsi": IndicatorSpec(
        name="rsi",
        display_name="RSI",
        default_params={"period": 14},
        overlay=False,
        y_axis="rsi",
        calculate=_rsi_calculate,
        series_meta={
            "rsi_{period}": {"type": "line", "color": "#52c41a"},
        },
    ),
    "macd": IndicatorSpec(
        name="macd",
        display_name="MACD",
        default_params={"fast": 12, "slow": 26, "signal": 9},
        overlay=False,
        y_axis="macd",
        calculate=_macd_calculate,
        series_meta={
            "macd_{fast}_{slow}_{signal}": {"type": "line", "color": "#1890ff"},
            "macd_signal_{fast}_{slow}_{signal}": {"type": "line", "color": "#faad14"},
            "macd_hist_{fast}_{slow}_{signal}": {"type": "bar", "color": ["#52c41a", "#ff4d4f"]},
        },
    ),
    "bollinger": IndicatorSpec(
        name="bollinger",
        display_name="Bollinger Bands",
        default_params={"period": 20, "std_dev": 2},
        overlay=True,
        y_axis=None,
        calculate=_bbands_calculate,
        series_meta={
            "bb_upper_{period}_{std_dev}": {"type": "line", "color": "#eb2f96"},
            "bb_middle_{period}_{std_dev}": {"type": "line", "color": "#722ed1"},
            "bb_lower_{period}_{std_dev}": {"type": "line", "color": "#eb2f96"},
        },
    ),
    "kdj": IndicatorSpec(
        name="kdj",
        display_name="KDJ",
        default_params={"k_period": 14, "k_smooth": 3, "d_smooth": 3},
        overlay=False,
        y_axis="kdj",
        calculate=_kdj_calculate,
        series_meta={
            "kdj_k_{k_period}_{k_smooth}_{d_smooth}": {"type": "line", "color": "#1890ff"},
            "kdj_d_{k_period}_{k_smooth}_{d_smooth}": {"type": "line", "color": "#faad14"},
            "kdj_j_{k_period}_{k_smooth}_{d_smooth}": {"type": "line", "color": "#52c41a"},
        },
    ),
    "skewness": IndicatorSpec(
        name="skewness",
        display_name="Skewness",
        default_params={"period": 20},
        overlay=False,
        y_axis="skewness",
        calculate=_skewness_calculate,
        series_meta={
            "skewness_{period}": {"type": "line", "color": "#13c2c2"},
        },
    ),
    "kurtosis": IndicatorSpec(
        name="kurtosis",
        display_name="Kurtosis",
        default_params={"period": 20},
        overlay=False,
        y_axis="kurtosis",
        calculate=_kurtosis_calculate,
        series_meta={
            "kurtosis_{period}": {"type": "line", "color": "#722ed1"},
        },
    ),
    "support": IndicatorSpec(
        name="support",
        display_name="Support",
        default_params={"period": 20},
        overlay=True,
        y_axis=None,
        calculate=_support_calculate,
        series_meta={
            "support_{period}": {"type": "line", "color": "#52c41a"},
        },
    ),
    "breakout": IndicatorSpec(
        name="breakout",
        display_name="Breakout",
        default_params={"period": 20},
        overlay=True,
        y_axis=None,
        calculate=_breakout_calculate,
        series_meta={
            "breakout_{period}": {"type": "line", "color": "#f5222d"},
        },
    ),
}


def list_available_indicators() -> List[Dict[str, Any]]:
    """返回所有可用指标的描述信息，供前端动态渲染选择器。"""
    result = []
    for name, spec in INDICATOR_REGISTRY.items():
        result.append({
            "name": spec.name,
            "display_name": spec.display_name,
            "default_params": spec.default_params,
            "overlay": spec.overlay,
            "y_axis": spec.y_axis,
            "series_meta": spec.series_meta,
        })
    return result

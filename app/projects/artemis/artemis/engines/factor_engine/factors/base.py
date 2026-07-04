"""因子基类与工具函数。"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd

from artemis.engines.factor_engine.ttm import compute_ttm, compute_single_quarter


# ---------------------------------------------------------------------------
# Safe math helpers
# ---------------------------------------------------------------------------

def safe_div(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:
    """安全除法，分母为 None / 0 / NaN 时返回 None。"""
    if numerator is None or denominator is None:
        return None
    if isinstance(numerator, float) and math.isnan(numerator):
        return None
    if isinstance(denominator, float) and (math.isnan(denominator) or abs(denominator) < 1e-12):
        return None
    if abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def avg_balance(
    df: Optional[pd.DataFrame],
    field: str,
    current_period: str,
) -> Optional[float]:
    """资产负债表期初期末均值 (当期 + 上期) / 2。"""
    if df is None or df.empty:
        return None
    from artemis.engines.factor_engine.ttm import _val, get_year, get_quarter, make_period

    year = get_year(current_period)
    quarter = get_quarter(current_period)
    if quarter == 0:
        return None

    cur = _val(df, current_period, field)

    # 上一期 = 上一季度末
    if quarter == 1:
        prev_period = f"{year - 1}1231"
    else:
        prev_period = make_period(year, quarter - 1)

    prev = _val(df, prev_period, field)

    if cur is None or prev is None:
        return cur  # fallback: 只有当期时直接用当期
    return (cur + prev) / 2.0


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseFactor(ABC):
    """所有因子组的抽象基类。"""

    @abstractmethod
    def factor_metas(self) -> list:
        """返回本组所有 FactorMeta 对象（用于注册）。"""

    @abstractmethod
    def compute(
        self,
        security_id: int,
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None,
        current_period: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        """计算单只股票的因子值。security_id is the registry identity (Phase 4)."""

    def compute_batch(
        self,
        security_ids: List[int],
        financial_data: Dict[int, Dict[str, pd.DataFrame]],
        market_data: Optional[Dict[int, pd.DataFrame]] = None,
        current_periods: Optional[Dict[int, str]] = None,
    ) -> pd.DataFrame:
        """批量计算多只股票的因子值。"""
        rows = {}
        for sec_id in security_ids:
            sym_fin = financial_data.get(sec_id, {})
            sym_mkt = market_data.get(sec_id) if market_data else None
            period = current_periods.get(sec_id) if current_periods else None
            rows[sec_id] = self.compute(sec_id, sym_fin, sym_mkt, period)
        return pd.DataFrame.from_dict(rows, orient="index")


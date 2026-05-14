"""成长性因子组 — Revenue/NI Growth YoY, CAGR 3Y, OCF Growth。"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from artemis.engines.factor_engine.factors.base import BaseFactor
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import register_factor
from artemis.engines.factor_engine.ttm import compute_ttm, compute_single_quarter, get_year, get_quarter, make_period

_METAS: List[FactorMeta] = [
    FactorMeta("revenue_growth_yoy", "营收同比增长", FactorCategory.GROWTH,
               "REV_SQ(t)/REV_SQ(t-4Q)-1", ("income",), ttm_required=False, unit="%", min_history_quarters=4),
    FactorMeta("ni_growth_yoy", "净利润同比增长", FactorCategory.GROWTH,
               "NI_SQ(t)/NI_SQ(t-4Q)-1", ("income",), ttm_required=False, unit="%", min_history_quarters=4),
    FactorMeta("revenue_cagr_3y", "3 年营收复合增长", FactorCategory.GROWTH,
               "(REV_TTM(t)/REV_TTM(t-12Q))^(1/3)-1", ("income",), ttm_required=True, unit="%", min_history_quarters=12),
    FactorMeta("ni_cagr_3y", "3 年净利润复合增长", FactorCategory.GROWTH,
               "(NI_TTM(t)/NI_TTM(t-12Q))^(1/3)-1", ("income",), ttm_required=True, unit="%", min_history_quarters=12),
    FactorMeta("ocf_growth", "经营现金流增长", FactorCategory.GROWTH,
               "OCF_TTM(t)/OCF_TTM(t-4Q)-1", ("cashflow",), ttm_required=True, unit="%", min_history_quarters=4),
]

for _m in _METAS:
    register_factor(_m)


def _growth_rate(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """计算增长率，处理负分母（亏损）的边界情况。"""
    if current is None or previous is None:
        return None
    if abs(previous) < 1e-12:
        return None
    if previous < 0:
        # 亏转盈或持续亏损的特殊处理
        return (current - previous) / abs(previous)
    return current / previous - 1.0


def _cagr(current: Optional[float], previous: Optional[float], years: int) -> Optional[float]:
    """复合年增长率。分母 ≤ 0 或分子 ≤ 0 时返回 None。"""
    if current is None or previous is None:
        return None
    if previous <= 0 or current <= 0:
        return None
    return (current / previous) ** (1.0 / years) - 1.0


class GrowthFactors(BaseFactor):

    def factor_metas(self) -> list:
        return list(_METAS)

    def compute(
        self,
        symbol: str,
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None,
        current_period: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        income = financial_data.get("income")
        cashflow = financial_data.get("cashflow")
        period = current_period or ""
        year = get_year(period) if period else 0
        quarter = get_quarter(period) if period else 0

        # 单季度同比
        prev_yoy_period = make_period(year - 1, quarter) if quarter else ""
        rev_sq_cur = compute_single_quarter(income, "OPERA_REV", period) if income is not None else None
        rev_sq_prev = compute_single_quarter(income, "OPERA_REV", prev_yoy_period) if income is not None else None
        ni_sq_cur = compute_single_quarter(income, "NET_PRO_EXCL_MIN_INT_INC", period) if income is not None else None
        ni_sq_prev = compute_single_quarter(income, "NET_PRO_EXCL_MIN_INT_INC", prev_yoy_period) if income is not None else None

        # CAGR 3Y (TTM based)
        period_3y_ago = make_period(year - 3, quarter) if quarter else ""
        rev_ttm_now = compute_ttm(income, "OPERA_REV", period) if income is not None else None
        rev_ttm_3y = compute_ttm(income, "OPERA_REV", period_3y_ago) if income is not None else None
        ni_ttm_now = compute_ttm(income, "NET_PRO_EXCL_MIN_INT_INC", period) if income is not None else None
        ni_ttm_3y = compute_ttm(income, "NET_PRO_EXCL_MIN_INT_INC", period_3y_ago) if income is not None else None

        # OCF Growth
        ocf_ttm_now = compute_ttm(cashflow, "NET_CASH_FLOW_OPERA_ACT", period) if cashflow is not None else None
        period_1y_ago = make_period(year - 1, quarter) if quarter else ""
        ocf_ttm_prev = compute_ttm(cashflow, "NET_CASH_FLOW_OPERA_ACT", period_1y_ago) if cashflow is not None else None

        return {
            "revenue_growth_yoy": _growth_rate(rev_sq_cur, rev_sq_prev),
            "ni_growth_yoy": _growth_rate(ni_sq_cur, ni_sq_prev),
            "revenue_cagr_3y": _cagr(rev_ttm_now, rev_ttm_3y, 3),
            "ni_cagr_3y": _cagr(ni_ttm_now, ni_ttm_3y, 3),
            "ocf_growth": _growth_rate(ocf_ttm_now, ocf_ttm_prev),
        }


"""质量因子组 — Accrual / Cash Conversion / FCF Quality / Earnings Stability / Goodwill。"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from artemis.engines.factor_engine.factors.base import BaseFactor, safe_div, avg_balance
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import register_factor
from artemis.engines.factor_engine.ttm import compute_ttm, compute_single_quarter, _val, get_year, get_quarter, make_period

_METAS: List[FactorMeta] = [
    FactorMeta("accrual_ratio", "应计比率", FactorCategory.QUALITY,
               "(NI_TTM - OCF_TTM) / avg(assets)", ("income", "cashflow", "balance_sheet"),
               ttm_required=True, higher_is_better=False),
    FactorMeta("cash_conversion", "现金转换率", FactorCategory.QUALITY,
               "OCF_TTM / NI_TTM", ("income", "cashflow"), ttm_required=True, unit="倍"),
    FactorMeta("fcf_quality", "自由现金流覆盖率", FactorCategory.QUALITY,
               "FCF_TTM / NI_TTM", ("income", "cashflow"), ttm_required=True, unit="倍"),
    FactorMeta("earnings_stability", "盈利稳定性", FactorCategory.QUALITY,
               "std(NI_SQ,8Q)/|mean(NI_SQ,8Q)|", ("income",),
               higher_is_better=False, min_history_quarters=8),
    FactorMeta("goodwill_ratio", "商誉占比", FactorCategory.QUALITY,
               "GOODWILL/TOTAL_ASSETS", ("balance_sheet",), higher_is_better=False, unit="%"),
]

for _m in _METAS:
    register_factor(_m)


class QualityFactors(BaseFactor):

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
        balance = financial_data.get("balance_sheet")
        period = current_period or ""

        ni_ttm = compute_ttm(income, "NET_PRO_EXCL_MIN_INT_INC", period) if income is not None else None
        ocf_ttm = compute_ttm(cashflow, "NET_CASH_FLOWS_OPER_ACT", period) if cashflow is not None else None
        assets_avg = avg_balance(balance, "TOTAL_ASSETS", period)

        # Accrual
        accrual = None
        if ni_ttm is not None and ocf_ttm is not None:
            accrual = safe_div(ni_ttm - ocf_ttm, assets_avg)

        # Cash Conversion & FCF Quality
        cash_conv = safe_div(ocf_ttm, ni_ttm)

        capex_ttm = compute_ttm(cashflow, "CASH_PAID_PUR_CONST_FIOLTA", period) if cashflow is not None else None
        fcf_ttm = (ocf_ttm - capex_ttm) if (ocf_ttm is not None and capex_ttm is not None) else None
        fcf_quality = safe_div(fcf_ttm, ni_ttm)

        # Earnings Stability
        stability = self._earnings_stability(income, period)

        # Goodwill
        goodwill = _val(balance, period, "GOODWILL") if balance is not None else None
        total_assets = _val(balance, period, "TOTAL_ASSETS") if balance is not None else None
        goodwill_ratio = safe_div(goodwill, total_assets)

        return {
            "accrual_ratio": accrual,
            "cash_conversion": cash_conv,
            "fcf_quality": fcf_quality,
            "earnings_stability": stability,
            "goodwill_ratio": goodwill_ratio,
        }

    @staticmethod
    def _earnings_stability(income: Optional[pd.DataFrame], period: str) -> Optional[float]:
        """CV of quarterly NI over 8 quarters, abs(mean) guard."""
        if income is None or not period:
            return None
        year = get_year(period)
        quarter = get_quarter(period)
        if quarter == 0:
            return None

        quarters = []
        y, q = year, quarter
        for _ in range(8):
            p = make_period(y, q)
            val = compute_single_quarter(income, "NET_PRO_EXCL_MIN_INT_INC", p)
            if val is not None:
                quarters.append(val)
            q -= 1
            if q == 0:
                q = 4
                y -= 1

        if len(quarters) < 4:
            return None

        import numpy as np
        arr = np.array(quarters, dtype=float)
        mean_abs = abs(arr.mean())
        std = arr.std(ddof=1)

        if mean_abs < 1e-8:
            return float(std)  # 退化：纯用 std
        return float(std / mean_abs)


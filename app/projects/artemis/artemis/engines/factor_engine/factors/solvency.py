"""偿债能力因子组。"""
from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd
from artemis.engines.factor_engine.factors.base import BaseFactor, safe_div
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import register_factor
from artemis.engines.factor_engine.ttm import compute_ttm, _val

_METAS: List[FactorMeta] = [
    FactorMeta("debt_ratio", "资产负债率", FactorCategory.SOLVENCY, "TOTAL_LIAB/TOTAL_ASSETS", ("balance_sheet",), higher_is_better=False, unit="%"),
    FactorMeta("current_ratio", "流动比率", FactorCategory.SOLVENCY, "CUR_ASSETS/CUR_LIAB", ("balance_sheet",), unit="倍", exclude_financial=True),
    FactorMeta("quick_ratio", "速动比率", FactorCategory.SOLVENCY, "(CUR_ASSETS-INV)/CUR_LIAB", ("balance_sheet",), unit="倍", exclude_financial=True),
    FactorMeta("interest_coverage", "利息保障倍数", FactorCategory.SOLVENCY, "EBIT_TTM/FIN_EXP_TTM", ("income",), ttm_required=True, unit="倍"),
    FactorMeta("net_debt_to_ebitda", "净负债/EBITDA", FactorCategory.SOLVENCY, "Net Debt/EBITDA_TTM", ("income", "balance_sheet"), ttm_required=True, higher_is_better=False, unit="倍"),
    FactorMeta("cash_to_st_debt", "现金覆盖短债", FactorCategory.SOLVENCY, "Cash / ST Debt", ("balance_sheet",), unit="倍"),
]
for _m in _METAS:
    register_factor(_m)

class SolvencyFactors(BaseFactor):
    def factor_metas(self) -> list:
        return list(_METAS)

    def compute(self, symbol: str, financial_data: Dict[str, pd.DataFrame],
                market_data: Optional[pd.DataFrame] = None, current_period: Optional[str] = None) -> Dict[str, Optional[float]]:
        balance = financial_data.get("balance_sheet")
        income = financial_data.get("income")
        p = current_period or ""

        total_liab = _val(balance, p, "TOTAL_LIAB") if balance is not None else None
        total_assets = _val(balance, p, "TOTAL_ASSETS") if balance is not None else None
        cur_assets = _val(balance, p, "TOTAL_CUR_ASSETS") if balance is not None else None
        cur_liab = _val(balance, p, "TOTAL_CUR_LIAB") if balance is not None else None
        inv = _val(balance, p, "INV") if balance is not None else None
        st_borrow = _val(balance, p, "ST_BORROWING") if balance is not None else None
        lt_loan = _val(balance, p, "LT_LOAN") if balance is not None else None
        cash = _val(balance, p, "CURRENCY_CAP") if balance is not None else None
        noncur_due = _val(balance, p, "NONCUR_LIAB_DUE_WITHIN_1Y") if balance is not None else None

        op_profit_ttm = compute_ttm(income, "OPERA_PROFIT", p) if income is not None else None
        fin_exp_ttm = compute_ttm(income, "LESS_FIN_EXP", p) if income is not None else None

        ebit_ttm = None
        if op_profit_ttm is not None and fin_exp_ttm is not None:
            ebit_ttm = op_profit_ttm + fin_exp_ttm

        # EBITDA ≈ EBIT + D&A (简化: 暂用 EBIT)
        ebitda_ttm = ebit_ttm

        net_debt = ((st_borrow or 0) + (lt_loan or 0) - (cash or 0))

        st_debt_total = (st_borrow or 0) + (noncur_due or 0)

        return {
            "debt_ratio": safe_div(total_liab, total_assets),
            "current_ratio": safe_div(cur_assets, cur_liab),
            "quick_ratio": safe_div((cur_assets - (inv or 0)) if cur_assets is not None else None, cur_liab),
            "interest_coverage": safe_div(ebit_ttm, fin_exp_ttm),
            "net_debt_to_ebitda": safe_div(net_debt, ebitda_ttm),
            "cash_to_st_debt": safe_div(cash, st_debt_total if st_debt_total > 1e-8 else None),
        }


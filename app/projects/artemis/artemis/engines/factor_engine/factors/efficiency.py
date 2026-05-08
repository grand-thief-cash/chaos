"""营运效率因子组。"""
from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd
from artemis.engines.factor_engine.factors.base import BaseFactor, safe_div, avg_balance
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import register_factor
from artemis.engines.factor_engine.ttm import compute_ttm

_METAS: List[FactorMeta] = [
    FactorMeta("asset_turnover", "总资产周转率", FactorCategory.EFFICIENCY, "REV_TTM/avg(Assets)", ("income", "balance_sheet"), ttm_required=True, unit="倍", exclude_financial=True),
    FactorMeta("inventory_turnover", "存货周转率", FactorCategory.EFFICIENCY, "COST_TTM/avg(INV)", ("income", "balance_sheet"), ttm_required=True, unit="倍", exclude_financial=True),
    FactorMeta("receivable_turnover", "应收账款周转率", FactorCategory.EFFICIENCY, "REV_TTM/avg(AR)", ("income", "balance_sheet"), ttm_required=True, unit="倍", exclude_financial=True),
    FactorMeta("cash_cycle", "现金循环天数", FactorCategory.EFFICIENCY, "DSO+DIO-DPO", ("income", "balance_sheet"), ttm_required=True, higher_is_better=False, unit="天", exclude_financial=True),
    FactorMeta("capex_to_revenue", "资本支出/营收", FactorCategory.EFFICIENCY, "Capex/REV_TTM", ("cashflow", "income"), ttm_required=True, higher_is_better=False, unit="%"),
]
for _m in _METAS:
    register_factor(_m)

class EfficiencyFactors(BaseFactor):
    def factor_metas(self) -> list:
        return list(_METAS)

    def compute(self, symbol: str, financial_data: Dict[str, pd.DataFrame],
                market_data: Optional[pd.DataFrame] = None, current_period: Optional[str] = None) -> Dict[str, Optional[float]]:
        income = financial_data.get("income")
        balance = financial_data.get("balance_sheet")
        cashflow = financial_data.get("cashflow")
        p = current_period or ""

        rev_ttm = compute_ttm(income, "OPERA_REV", p) if income is not None else None
        cost_ttm = compute_ttm(income, "LESS_OPERA_COST", p) if income is not None else None
        assets_avg = avg_balance(balance, "TOTAL_ASSETS", p)
        inv_avg = avg_balance(balance, "INV", p)
        ar_avg = avg_balance(balance, "ACCT_RECEIVABLE", p)
        ap_avg = avg_balance(balance, "ACCT_PAYABLE", p)

        at = safe_div(rev_ttm, assets_avg)
        it = safe_div(cost_ttm, inv_avg)
        rt = safe_div(rev_ttm, ar_avg)

        # DSO, DIO, DPO → cash cycle
        dso = safe_div(365.0, rt) if rt else None
        dio = safe_div(365.0, it) if it else None
        dpo = safe_div(365.0, safe_div(cost_ttm, ap_avg)) if cost_ttm and ap_avg else None
        cash_cycle = None
        if dso is not None and dio is not None and dpo is not None:
            cash_cycle = dso + dio - dpo

        capex_ttm = compute_ttm(cashflow, "CASH_PAID_PUR_CONST_FIOLTA", p) if cashflow is not None else None
        capex_rev = safe_div(capex_ttm, rev_ttm)

        return {
            "asset_turnover": at,
            "inventory_turnover": it,
            "receivable_turnover": rt,
            "cash_cycle": cash_cycle,
            "capex_to_revenue": capex_rev,
        }


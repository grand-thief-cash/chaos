"""每股指标因子组。"""
from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd
from artemis.engines.factor_engine.factors.base import BaseFactor, safe_div
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import register_factor
from artemis.engines.factor_engine.ttm import compute_ttm, _val

_METAS: List[FactorMeta] = [
    FactorMeta("eps_ttm", "每股收益TTM", FactorCategory.PER_SHARE, "NI_TTM/Shares", ("income",), ttm_required=True, requires_market_data=True),
    FactorMeta("bps", "每股净资产", FactorCategory.PER_SHARE, "Equity/Shares", ("balance_sheet",), requires_market_data=True),
    FactorMeta("cfps", "每股经营现金流", FactorCategory.PER_SHARE, "OCF_TTM/Shares", ("cashflow",), ttm_required=True, requires_market_data=True),
    FactorMeta("fcf_per_share", "每股自由现金流", FactorCategory.PER_SHARE, "FCF_TTM/Shares", ("cashflow",), ttm_required=True, requires_market_data=True),
    FactorMeta("dps", "每股股利", FactorCategory.PER_SHARE, "Cash Dividend Per Share", ("corporate_action",)),
]
for _m in _METAS:
    register_factor(_m)

def _total_shares(mkt: Optional[pd.DataFrame]) -> Optional[float]:
    if mkt is None or mkt.empty:
        return None
    if "total_share" in mkt.columns:
        v = mkt["total_share"].iloc[-1]
        return float(v) if v else None
    return None

class PerShareFactors(BaseFactor):
    def factor_metas(self) -> list:
        return list(_METAS)

    def compute(self, symbol: str, financial_data: Dict[str, pd.DataFrame],
                market_data: Optional[pd.DataFrame] = None, current_period: Optional[str] = None) -> Dict[str, Optional[float]]:
        income = financial_data.get("income")
        balance = financial_data.get("balance_sheet")
        cashflow = financial_data.get("cashflow")
        p = current_period or ""
        shares = _total_shares(market_data)
        if shares is None and balance is not None:
            shares = _val(balance, p, "TOT_SHARE")

        ni_ttm = compute_ttm(income, "NET_PRO_EXCL_MIN_INT_INC", p) if income is not None else None
        ocf_ttm = compute_ttm(cashflow, "NET_CASH_FLOW_OPERA_ACT", p) if cashflow is not None else None
        capex_ttm = compute_ttm(cashflow, "CASH_PAID_PUR_CONST_FIOLTA", p) if cashflow is not None else None
        equity = _val(balance, p, "TOT_SHARE_EQUITY_EXCL_MIN_INT") if balance is not None else None
        dps_val = None
        if market_data is not None and not market_data.empty and "dps" in market_data.columns:
            dps_val = float(market_data["dps"].iloc[-1])

        fcf_ttm = (ocf_ttm - capex_ttm) if (ocf_ttm is not None and capex_ttm is not None) else None

        return {
            "eps_ttm": safe_div(ni_ttm, shares),
            "bps": safe_div(equity, shares),
            "cfps": safe_div(ocf_ttm, shares),
            "fcf_per_share": safe_div(fcf_ttm, shares),
            "dps": dps_val,
        }


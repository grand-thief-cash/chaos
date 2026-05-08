"""估值因子组 — PE_TTM / PB / PS / PEG / EV-EBITDA / PCF / Dividend Yield。"""
from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd
from artemis.engines.factor_engine.factors.base import BaseFactor, safe_div
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import register_factor
from artemis.engines.factor_engine.ttm import compute_ttm, _val

_METAS: List[FactorMeta] = [
    FactorMeta("pe_ttm", "市盈率TTM", FactorCategory.VALUATION, "MC/NI_TTM", ("income",), requires_market_data=True, higher_is_better=False, unit="倍"),
    FactorMeta("pb", "市净率", FactorCategory.VALUATION, "MC/Equity", ("balance_sheet",), requires_market_data=True, higher_is_better=False, unit="倍"),
    FactorMeta("ps_ttm", "市销率TTM", FactorCategory.VALUATION, "MC/REV_TTM", ("income",), requires_market_data=True, higher_is_better=False, unit="倍"),
    FactorMeta("peg", "PEG", FactorCategory.VALUATION, "PE/Growth", ("income",), requires_market_data=True, higher_is_better=False),
    FactorMeta("ev_to_ebitda", "EV/EBITDA", FactorCategory.VALUATION, "EV/EBITDA_TTM", ("income", "balance_sheet"), requires_market_data=True, higher_is_better=False, unit="倍"),
    FactorMeta("pcf", "市现率", FactorCategory.VALUATION, "MC/OCF_TTM", ("cashflow",), requires_market_data=True, higher_is_better=False, unit="倍"),
    FactorMeta("dividend_yield", "股息率", FactorCategory.VALUATION, "DPS/Close", ("balance_sheet",), requires_market_data=True, unit="%"),
]
for _m in _METAS:
    register_factor(_m)


def _market_cap(mkt: Optional[pd.DataFrame]) -> Optional[float]:
    """从行情 DataFrame 取 market_cap 或 close×total_share。"""
    if mkt is None or mkt.empty:
        return None
    if "market_cap" in mkt.columns:
        return float(mkt["market_cap"].iloc[-1])
    if "close" in mkt.columns and "total_share" in mkt.columns:
        c = mkt["close"].iloc[-1]
        s = mkt["total_share"].iloc[-1]
        if c and s:
            return float(c) * float(s)
    return None


class ValuationFactors(BaseFactor):
    def factor_metas(self) -> list:
        return list(_METAS)

    def compute(self, symbol: str, financial_data: Dict[str, pd.DataFrame],
                market_data: Optional[pd.DataFrame] = None, current_period: Optional[str] = None) -> Dict[str, Optional[float]]:
        income = financial_data.get("income")
        balance = financial_data.get("balance_sheet")
        cashflow = financial_data.get("cashflow")
        p = current_period or ""

        mc = _market_cap(market_data)

        ni_ttm = compute_ttm(income, "NET_PRO_EXCL_MIN_INT_INC", p) if income is not None else None
        rev_ttm = compute_ttm(income, "OPERA_REV", p) if income is not None else None
        ocf_ttm = compute_ttm(cashflow, "NET_CASH_FLOWS_OPER_ACT", p) if cashflow is not None else None
        equity = _val(balance, p, "TOT_SHARE_EQUITY_EXCL_MIN_INT") if balance is not None else None

        pe = safe_div(mc, ni_ttm) if (ni_ttm is not None and ni_ttm > 0) else None
        pb = safe_div(mc, equity)
        ps = safe_div(mc, rev_ttm)
        pcf = safe_div(mc, ocf_ttm) if (ocf_ttm is not None and ocf_ttm > 0) else None

        # PEG: pe / (growth × 100). growth 是 ni_growth_yoy (需要外部传入或这里自行计算)
        # 简化: 暂时返回 None, 等 pipeline 层组合时再算
        peg = None

        # EV/EBITDA
        ev_ebitda = None
        if mc is not None:
            st_borrow = _val(balance, p, "ST_BORROWING") or 0
            lt_loan = _val(balance, p, "LT_LOAN") or 0
            bonds = _val(balance, p, "BONDS_PAYABLE") or 0
            cash = _val(balance, p, "CURRENCY_CAP") or 0
            ev = mc + st_borrow + lt_loan + bonds - cash
            op_ttm = compute_ttm(income, "OPERA_PROFIT", p) if income is not None else None
            fin_ttm = compute_ttm(income, "LESS_FIN_EXP", p) if income is not None else None
            ebitda = (op_ttm + fin_ttm) if (op_ttm is not None and fin_ttm is not None) else None
            ev_ebitda = safe_div(ev, ebitda)

        # Dividend Yield
        close_price = None
        if market_data is not None and not market_data.empty and "close" in market_data.columns:
            close_price = float(market_data["close"].iloc[-1])
        dps = _val(balance, p, "DPS") if balance is not None else None
        div_yield = safe_div(dps, close_price)

        return {
            "pe_ttm": pe,
            "pb": pb,
            "ps_ttm": ps,
            "peg": peg,
            "ev_to_ebitda": ev_ebitda,
            "pcf": pcf,
            "dividend_yield": div_yield,
        }


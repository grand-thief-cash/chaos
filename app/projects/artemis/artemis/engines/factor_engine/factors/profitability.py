"""盈利能力因子组 — ROE / ROA / Gross Margin / Operating Margin / Net Margin / ROIC。"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from artemis.engines.factor_engine.factors.base import BaseFactor, safe_div, avg_balance
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import register_factor
from artemis.engines.factor_engine.ttm import compute_ttm

_METAS: List[FactorMeta] = [
    FactorMeta("roe", "净资产收益率", FactorCategory.PROFITABILITY,
               "NI_TTM / avg(equity)", ("income", "balance_sheet"), ttm_required=True, unit="%"),
    FactorMeta("roa", "总资产收益率", FactorCategory.PROFITABILITY,
               "NI_TTM / avg(total_assets)", ("income", "balance_sheet"), ttm_required=True, unit="%"),
    FactorMeta("gross_margin", "毛利率", FactorCategory.PROFITABILITY,
               "(REV_TTM - COST_TTM) / REV_TTM", ("income",), ttm_required=True, unit="%"),
    FactorMeta("operating_margin", "营业利润率", FactorCategory.PROFITABILITY,
               "OPERA_PROFIT_TTM / REV_TTM", ("income",), ttm_required=True, unit="%"),
    FactorMeta("net_margin", "净利率", FactorCategory.PROFITABILITY,
               "NI_TTM / REV_TTM", ("income",), ttm_required=True, unit="%"),
    FactorMeta("roic", "投入资本回报率", FactorCategory.PROFITABILITY,
               "NOPAT / Invested Capital", ("income", "balance_sheet"),
               ttm_required=True, unit="%", exclude_financial=True),
]

for _m in _METAS:
    register_factor(_m)


class ProfitabilityFactors(BaseFactor):

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
        balance = financial_data.get("balance_sheet")
        period = current_period or ""

        ni_ttm = compute_ttm(income, "NET_PRO_EXCL_MIN_INT_INC", period) if income is not None else None
        rev_ttm = compute_ttm(income, "OPERA_REV", period) if income is not None else None
        cost_ttm = compute_ttm(income, "LESS_OPERA_COST", period) if income is not None else None
        op_profit_ttm = compute_ttm(income, "OPERA_PROFIT", period) if income is not None else None

        equity_avg = avg_balance(balance, "TOT_SHARE_EQUITY_EXCL_MIN_INT", period)
        assets_avg = avg_balance(balance, "TOTAL_ASSETS", period)

        roe = safe_div(ni_ttm, equity_avg)
        roa = safe_div(ni_ttm, assets_avg)
        gross_margin = safe_div((rev_ttm - cost_ttm) if (rev_ttm is not None and cost_ttm is not None) else None, rev_ttm)
        operating_margin = safe_div(op_profit_ttm, rev_ttm)
        net_margin = safe_div(ni_ttm, rev_ttm)

        # ROIC = NOPAT / Invested Capital (不适用于金融行业 → 调用层通过 exclude_financial 过滤)
        roic = self._compute_roic(income, balance, period, op_profit_ttm)

        return {
            "roe": roe,
            "roa": roa,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "net_margin": net_margin,
            "roic": roic,
        }

    @staticmethod
    def _compute_roic(
        income: Optional[pd.DataFrame],
        balance: Optional[pd.DataFrame],
        period: str,
        op_profit_ttm: Optional[float],
    ) -> Optional[float]:
        """计算投入资本回报率（ROIC）。

        公式：ROIC = NOPAT / Invested Capital

        其中：
        - NOPAT = 营业利润（TTM） * (1 - 有效税率)
          有效税率从最近的年度报告中计算：income 中对应年度的 INCOME_TAX / TOTAL_PROFIT，
          并被限制在 [0.0, 0.5] 范围内；若无法计算则使用回退值 0.25。
        - Invested Capital = 股东权益 + 带息负债 - 货币资金
          这里带息负债由短期借款（ST_BORROWING）、长期借款（LT_LOAN）和应付债券（BONDS_PAYABLE）相加得到，
          货币资金使用 CURRENCY_CAP 字段。

        参数：
        - income: 利润表 DataFrame，用于读取税费与利润等年度数据
        - balance: 资产负债表 DataFrame，用于读取股东权益、借款与现金等字段
        - period: 当前期间字符串（如 'YYYYMMDD' 或 'YYYY1231'），用于选择对应报表行
        - op_profit_ttm: 营业利润的 TTM 值（由外部 compute_ttm 提供）

        返回：
        - ROIC（以小数表示，例如 0.12 表示 12%），若输入数据不足或无法计算则返回 None。

        说明：该方法不适用于金融行业（调用方通过 exclude_financial 进行过滤）。
        """

        if income is None or balance is None or op_profit_ttm is None:
            return None
        from artemis.engines.factor_engine.ttm import _val

        # effective tax rate from latest annual report
        year = int(period[:4]) if len(period) >= 4 else 0
        annual_period = f"{year - 1}1231" if period[4:] != "1231" else period
        tax = _val(income, annual_period, "INCOME_TAX")
        pretax = _val(income, annual_period, "TOTAL_PROFIT")
        if tax is None or pretax is None or abs(pretax) < 1e-8:
            tax_rate = 0.25  # fallback
        else:
            tax_rate = max(0.0, min(tax / pretax, 0.5))

        nopat = op_profit_ttm * (1.0 - tax_rate)

        # Invested Capital = equity + interest-bearing debt - cash
        equity = _val(balance, period, "TOT_SHARE_EQUITY_EXCL_MIN_INT")
        st_borrowing = _val(balance, period, "ST_BORROWING") or 0.0
        lt_loan = _val(balance, period, "LT_LOAN") or 0.0
        bonds = _val(balance, period, "BONDS_PAYABLE") or 0.0
        cash = _val(balance, period, "CURRENCY_CAP") or 0.0

        if equity is None:
            return None
        invested = equity + st_borrowing + lt_loan + bonds - cash
        return safe_div(nopat, invested)


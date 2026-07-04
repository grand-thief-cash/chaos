"""DuPont analysis — artemis-owned business computation.

artemis-owned business computation. Fetches income + balance_sheet (all
report_type periods) from phoenixA, then derives the DuPont decomposition tree
for 4 kinds:
- annual (全年)
- single_quarter (单季度)
- ytd (年初至今累计)
- ttm (滚动12个月，默认)

When period_kind=ytd and target_period is Q3 (report_type=3), also supports
extrapolate_q4=True to estimate full year as Q3 YTD × 4/3.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Literal

from artemis.log.logger import get_logger
from artemis.models.bi import (
    BIDetailEquation,
    BIDetailStack,
    BIDetailStackRow,
    BIDriverItem,
    BIDupontMetricNode,
    BIDupontResponse,
    BIDupontTreeNode,
)
from artemis.services.bi.base import BIServiceBase

logger = get_logger("bi_service")


class DupontMixin(BIServiceBase):
    """DuPont decomposition computation over phoenixA income + balance data."""

    # Field lists projected from phoenixA (top_level + data_json mix).
    _DUPONT_INCOME_FIELDS: List[str] = [
        "reporting_period", "report_type", "security_name",
        "TOT_OPERA_REV", "OPERA_PROFIT", "NET_PRO_EXCL_MIN_INT_INC",
        "LESS_OPERA_COST", "LESS_BUS_TAX_SURCHARGE",
        "LESS_SELLING_EXP", "LESS_ADMIN_EXP", "LESS_FIN_EXP", "RD_EXP",
        "LESS_ASSETS_IMPAIR_LOSS",
        "PLUS_NET_INV_INC", "PLUS_NET_GAIN_CHG_FV", "GAIN_DISPOSAL_ASSETS",
        "OTH_INCOME",
    ]
    _DUPONT_BALANCE_FIELDS: List[str] = [
        "reporting_period", "report_type", "security_name",
        "TOTAL_ASSETS", "TOTAL_LIAB", "TOT_SHARE_EQUITY_EXCL_MIN_INT",
        "TOTAL_CUR_ASSETS", "TOT_NONCUR_ASSETS",
        "INV", "ACCT_RECEIVABLE", "PREPAYMENT", "CURRENCY_CAP",
        "ST_BORROWING", "ACCT_PAYABLE", "ADV_RECEIPT", "LT_LOAN", "LEASE_LIABILITY",
        "FIXED_ASSETS", "INTANGIBLE_ASSETS", "GOODWILL", "DEFERRED_TAX_ASSETS",
        "LT_EQUITY_INV",
    ]

    # Income flow fields that are recomputed when synthesizing a transformed
    # income row (TTM sum, single-quarter subtraction, Q3 extrapolation scale).
    # Shared so the detail stacks/equations stay on the same caliber as the
    # computed ratios.
    _INCOME_FLOW_FIELDS: List[str] = [
        "TOT_OPERA_REV", "NET_PRO_EXCL_MIN_INT_INC",
        "LESS_OPERA_COST", "LESS_BUS_TAX_SURCHARGE",
        "LESS_SELLING_EXP", "LESS_ADMIN_EXP", "LESS_FIN_EXP", "RD_EXP",
        "LESS_ASSETS_IMPAIR_LOSS",
        "PLUS_NET_INV_INC", "PLUS_NET_GAIN_CHG_FV", "GAIN_DISPOSAL_ASSETS",
        "OTH_INCOME",
    ]

    def get_dupont_analysis(
        self,
        *,
        symbol: str = "",
        security_id: Optional[int] = None,
        source: str = "amazing_data",
        market: str = "zh_a",
        statement_code: str = "1",
        period_kind: Literal["annual", "single_quarter", "ytd", "ttm"] = "ttm",
        target_reporting_period: Optional[str] = None,
        extrapolate_q4: bool = False,
    ) -> Dict[str, Any]:
        """Compute a DuPont decomposition for one security/period.

        Identity is security_id (Phase 4); `symbol` is convenience input
        resolved to security_id by query_financial (refactor §8.bis-5). One of
        security_id/symbol is required. `symbol` is also carried in the response
        for display (empty when only security_id is supplied).

        Parameters:
            period_kind: "annual" (全年)/"single_quarter" (单季度)/"ytd" (年初至今)/"ttm" (滚动12个月，默认)
            target_reporting_period: 指定目标报告期YYYY-MM-DD，默认取最新可用期
            extrapolate_q4: 仅当period_kind=ytd且target_period是Q3(report_type=3)时生效，按Q3YTD×4/3外推全年预测
        """
        if not security_id and not symbol:
            raise ValueError("get_dupont_analysis requires security_id or symbol")
        # Step 1: fetch all periods (all report_type)
        income_rows = self._fetch_all_dupont_rows(
            source=source, statement_type="income", security_id=security_id, symbol=symbol,
            market=market, statement_code=statement_code,
            fields=self._DUPONT_INCOME_FIELDS,
        )
        balance_rows = self._fetch_all_dupont_rows(
            source=source, statement_type="balance_sheet", security_id=security_id, symbol=symbol,
            market=market, statement_code=statement_code,
            fields=self._DUPONT_BALANCE_FIELDS,
        )

        if not income_rows or not balance_rows:
            raise ValueError(f"no financial data for dupont: symbol={symbol}")

        # Step 2: build period maps
        inc_map = self._build_period_map(income_rows)
        bal_map = self._build_period_map(balance_rows)

        # Step 3: pick target period
        if not target_reporting_period:
            if period_kind == "annual":
                # annual needs an rt=4 (年报) period; fall back to latest overall
                target_reporting_period = self._pick_latest_period_by_rt(income_rows, "4") \
                    or self._pick_latest_period(income_rows)
            else:
                target_reporting_period = self._pick_latest_period(income_rows)
        if not target_reporting_period:
            raise ValueError(f"no available period for symbol {symbol}")

        # Step 4: compute core DuPont
        result, ctx = self._compute_dupont_by_kind(
            period_kind=period_kind, symbol=symbol, source=source, market=market,
            statement_code=statement_code,
            target_period=target_reporting_period, inc_map=inc_map, bal_map=bal_map,
        )

        # Step 5: Q3 extrapolation if requested
        if period_kind == "ytd" and extrapolate_q4 and self._is_q3(result["report_type"]):
            # Extrapolate: YTD × 4/3, keep same balance avg
            result["extrapolated_full_year"] = self._extrapolate_q3_full_year(
                result, ctx, inc_map=inc_map, bal_map=bal_map,
            )

        return result

    # ─── DuPont helpers ───

    def _fetch_all_dupont_rows(
        self,
        *,
        source: str,
        statement_type: str,
        symbol: str,
        market: str,
        statement_code: str,
        fields: List[str],
        security_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all report_type periods, sorted newest first.

        Paginates through every available period so a symbol with >150 periods
        is not silently truncated. A single symbol's annual + quarterly history
        is well under one page in practice, but we page defensively.
        """
        rows: List[Dict[str, Any]] = []
        page, page_size = 1, 200
        while True:
            resp = self.query_financial(
                source=source, statement_type=statement_type,
                security_id=security_id, symbol=symbol,
                market=market, fields=",".join(fields), format="flat",
                period_start=None, period_end=None,
                report_type=None, statement_code=statement_code,
                page=page, page_size=page_size,
            )
            page_rows = resp.get("rows") if isinstance(resp, dict) else None
            if not page_rows:
                break
            rows.extend(page_rows)
            # Stop once we've consumed the full result set.
            total = resp.get("total") if isinstance(resp, dict) else None
            if (total is not None and len(rows) >= total) or len(page_rows) < page_size:
                break
            page += 1
            if page > 200:  # hard backstop against runaway paging
                logger.warning({"event": "dupont_fetch_paging_backstop", "symbol": symbol, "pages": page})
                break
        if not rows:
            return []
        return sorted(rows, key=lambda r: r.get("reporting_period") or "", reverse=True)

    @staticmethod
    def _pick_latest_period(rows: List[Dict[str, Any]]) -> Optional[str]:
        return rows[0].get("reporting_period") if rows else None

    @staticmethod
    def _pick_latest_period_by_rt(rows: List[Dict[str, Any]], rt: str) -> Optional[str]:
        """Latest reporting_period among rows with the given report_type."""
        for r in rows:  # rows are sorted newest-first
            if str(r.get("report_type", "")) == rt:
                return r.get("reporting_period")
        return None

    @staticmethod
    def _build_period_map(rows: List[Dict[str, Any]]) -> Dict[Tuple[int, str], Dict[str, Any]]:
        """Key: (year, report_type) where year is from reporting_period, report_type is '1','2','3','4'."""
        period_map: Dict[Tuple[int, str], Dict[str, Any]] = {}
        for r in rows:
            rp = r.get("reporting_period")
            rt = str(r.get("report_type", ""))
            if rp and rt:
                year = int(rp.split("-")[0])
                key = (year, rt)
                period_map[key] = r
        return period_map

    @staticmethod
    def _is_q3(report_type: str) -> bool:
        return str(report_type) == "3"

    @staticmethod
    def _year_and_month(period: str) -> Tuple[int, int]:
        y, m = int(period.split("-")[0]), int(period.split("-")[1])
        return y, m

    def _get_prev_quarter_in_year(
        self,
        year: int,
        rt: str,
        period_map: Dict[Tuple[int, str], Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Get previous quarter in same year (e.g., Q2 for Q3; Q1 for Q2; None for Q1)."""
        rt = str(rt)
        rt_order = {"1": None, "2": "1", "3": "2", "4": None}
        prev_rt = rt_order.get(rt)
        if not prev_rt:
            return None
        return period_map.get((year, prev_rt))

    def _compute_dupont_by_kind(
        self,
        *,
        period_kind: Literal["annual", "single_quarter", "ytd", "ttm"],
        symbol: str,
        source: str,
        market: str,
        statement_code: str,
        target_period: str,
        inc_map: Dict[Tuple[int, str], Dict[str, Any]],
        bal_map: Dict[Tuple[int, str], Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Parse target period's year and report_type
        target_year, _ = self._year_and_month(target_period)
        target_rt = self._find_rt_by_period(inc_map, target_period)
        if not target_rt:
            target_rt = self._find_rt_by_period(bal_map, target_period)
        if not target_rt:
            raise ValueError(f"no report_type found for period {target_period}")

        # Current period ratios + the income/balance rows used for detail stacks
        cur, inc_cur, bal_cur = self._ratios_for(
            period_kind=period_kind, target_period=target_period,
            inc_map=inc_map, bal_map=bal_map,
        )
        if cur is None:
            raise ValueError(f"insufficient data for period {target_period} ({period_kind})")

        # Prior period for delta/趋势 comparison. Semantics per kind:
        #   annual          → prior year annual          (同比)
        #   ytd             → prior year same-period YTD (同比)
        #   single_quarter  → immediately preceding single quarter (环比)
        #   ttm             → immediately preceding reporting period's TTM (环比)
        prev_period = self._prior_period_for_delta(period_kind, target_period, target_rt)
        prev = None
        if prev_period:
            prev_ratios, _, _ = self._ratios_for(
                period_kind=period_kind, target_period=prev_period,
                inc_map=inc_map, bal_map=bal_map,
            )
            prev = prev_ratios

        # Build response
        result = self._build_dupont_response(
            period_kind=period_kind, target_reporting_period=target_period,
            symbol=symbol, source=source, market=market,
            report_type=target_rt, statement_code=statement_code,
            inc_cur=inc_cur, bal_cur=bal_cur, cur=cur, prev=prev,
            prev_period=prev_period,
        )
        # Carry the intermediate rows/ratios for Q3 extrapolation (not exposed
        # in the HTTP response — see _build_dupont_response).
        ctx = {
            "inc_cur": inc_cur, "bal_cur": bal_cur, "cur": cur, "prev": prev,
            "prev_period": prev_period,
        }
        return result, ctx

    def _ratios_for(
        self,
        *,
        period_kind: Literal["annual", "single_quarter", "ytd", "ttm"],
        target_period: str,
        inc_map: Dict[Tuple[int, str], Dict[str, Any]],
        bal_map: Dict[Tuple[int, str], Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Optional[float]]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Compute the DuPont ratio dict for one (period, kind).

        Returns (ratios, inc_cur, bal_cur) where inc_cur/bal_cur are the rows
        used for the detail stacks (for the current kind they are the current
        period's rows; prev-period detail stacks are not rendered, so the rows
        are only needed for the current call).
        """
        target_year, _ = self._year_and_month(target_period)
        target_rt = self._find_rt_by_period(inc_map, target_period) \
            or self._find_rt_by_period(bal_map, target_period)
        if not target_rt:
            return None, None, None

        inc_cur: Optional[Dict[str, Any]] = None
        inc_prev_period: Optional[Dict[str, Any]] = None
        bal_cur: Optional[Dict[str, Any]] = None
        bal_prev_denom: Optional[Dict[str, Any]] = None

        if period_kind == "annual":
            inc_cur = inc_map.get((target_year, "4"))
            bal_cur = bal_map.get((target_year, "4"))
            bal_prev_denom = bal_map.get((target_year - 1, "4"))
        elif period_kind == "single_quarter":
            inc_cur = inc_map.get((target_year, target_rt))
            bal_cur = bal_map.get((target_year, target_rt))
            prev_rt = {"2": "1", "3": "2", "4": "3"}.get(target_rt)
            if prev_rt:
                inc_prev_period = inc_map.get((target_year, prev_rt))
                bal_prev_denom = bal_map.get((target_year, prev_rt))
            else:
                # Q1: single quarter = Q1 YTD itself; balance avg = (Q1, prior year Q4)
                prev_q4 = bal_map.get((target_year - 1, "4"))
                bal_prev_denom = prev_q4 if prev_q4 else bal_cur
        elif period_kind == "ytd":
            inc_cur = inc_map.get((target_year, target_rt))
            bal_cur = bal_map.get((target_year, target_rt))
            bal_prev_denom = bal_map.get((target_year - 1, "4"))
        elif period_kind == "ttm":
            inc_ytd = inc_map.get((target_year, target_rt))
            inc_prev_year = inc_map.get((target_year - 1, "4"))
            inc_prev_ytd = inc_map.get((target_year - 1, target_rt))
            inc_cur = self._synthesize_ttm_income(inc_ytd, inc_prev_year, inc_prev_ytd)
            bal_cur = bal_map.get((target_year, target_rt))
            bal_prev_denom = bal_map.get((target_year - 1, "4"))

        if inc_cur is None or bal_cur is None:
            return None, inc_cur, bal_cur

        ratios = self._compute_period_ratios(
            period_kind=period_kind,
            inc_cur=inc_cur, inc_prev_period=inc_prev_period,
            bal_cur=bal_cur, bal_prev_denom=bal_prev_denom,
        )
        # Detail stacks/equations need an income row on the SAME caliber as
        # `ratios`. For single_quarter the ratios use a single-quarter value
        # (YTD − prior YTD) while `inc_cur` is still the YTD row — synthesize a
        # single-quarter row so the breakdown stacks stay consistent. Other
        # kinds already use `inc_cur` at the right caliber.
        detail_inc = inc_cur
        if period_kind == "single_quarter":
            detail_inc = self._synthesize_single_quarter_income(inc_cur, inc_prev_period)
        return ratios, detail_inc, bal_cur

    @staticmethod
    def _prior_period_for_delta(
        period_kind: Literal["annual", "single_quarter", "ytd", "ttm"],
        target_period: str,
        target_rt: str,
    ) -> Optional[str]:
        """Return the prior reporting_period used for delta/趋势, by kind.

        annual/ytd → 同比 (prior year same period); single_quarter/ttm → 环比
        (immediately preceding reporting period). Returns None if it would be
        the same period (no prior available).
        """
        rt = str(target_rt)
        if period_kind in ("annual", "ytd"):
            y, m, d = target_period.split("-")
            return f"{int(y) - 1}-{m}-{d}"
        # 环比: preceding reporting period
        y = int(target_period.split("-")[0])
        seq = {"1": (y - 1, "4"), "2": (y, "1"), "3": (y, "2"), "4": (y, "3")}
        py, prt = seq.get(rt, (y, rt))
        month_day = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}[prt]
        return f"{py}-{month_day}"

    def _synthesize_ttm_income(
        self,
        inc_cur: Optional[Dict[str, Any]],
        inc_prev_year_full: Optional[Dict[str, Any]],
        inc_prev_ytd: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Synthesize TTM income: current YTD + prior full year - prior YTD."""
        if not inc_cur or not inc_prev_year_full or not inc_prev_ytd:
            return None
        # Clone a dict and compute synthetic fields:
        synth = dict(inc_cur)
        for field in self._INCOME_FLOW_FIELDS:
            cv = self._to_float(inc_cur.get(field))
            pfv = self._to_float(inc_prev_year_full.get(field))
            pyv = self._to_float(inc_prev_ytd.get(field))
            synv = None
            if cv is not None and pfv is not None and pyv is not None:
                synv = cv + pfv - pyv
            synth[field] = str(synv) if synv is not None else ""
        return synth

    def _synthesize_single_quarter_income(
        self,
        inc_ytd: Optional[Dict[str, Any]],
        inc_prev_ytd: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Synthesize a single-quarter income row: YTD − prior-period YTD.

        For Q1 (no in-year prior period) the single quarter equals Q1 YTD, so
        the row is returned unchanged. Used so detail stacks/equations share the
        same single-quarter caliber as the computed ratios.
        """
        if not inc_ytd:
            return None
        if not inc_prev_ytd:
            return dict(inc_ytd)
        synth = dict(inc_ytd)
        for field in self._INCOME_FLOW_FIELDS:
            cv = self._to_float(inc_ytd.get(field))
            pv = self._to_float(inc_prev_ytd.get(field))
            if cv is not None and pv is not None:
                synth[field] = str(cv - pv)
            elif cv is not None:
                synth[field] = str(cv)
            else:
                synth[field] = ""
        return synth

    def _scale_income_row(
        self,
        inc_row: Optional[Dict[str, Any]],
        factor: float,
    ) -> Optional[Dict[str, Any]]:
        """Clone inc_row with every income flow field scaled by `factor`."""
        if not inc_row:
            return None
        synth = dict(inc_row)
        for field in self._INCOME_FLOW_FIELDS:
            v = self._to_float(inc_row.get(field))
            synth[field] = str(v * factor) if v is not None else ""
        return synth

    def _compute_period_ratios(
        self,
        period_kind: str,
        inc_cur: Optional[Dict[str, Any]],
        inc_prev_period: Optional[Dict[str, Any]],
        bal_cur: Optional[Dict[str, Any]],
        bal_prev_denom: Optional[Dict[str, Any]],
    ) -> Dict[str, Optional[float]]:
        """Compute net_profit/revenue/avg_assets/avg_equity based on period_kind."""
        net_profit = self._get_net_profit(period_kind, inc_cur, inc_prev_period)
        revenue = self._get_revenue(period_kind, inc_cur, inc_prev_period)

        total_assets = self._amount(bal_cur, "TOTAL_ASSETS") if bal_cur else None
        total_liab = self._amount(bal_cur, "TOTAL_LIAB") if bal_cur else None
        equity = self._amount(bal_cur, "TOT_SHARE_EQUITY_EXCL_MIN_INT") if bal_cur else None

        total_assets_prev_denom = self._amount(bal_prev_denom, "TOTAL_ASSETS") if bal_prev_denom else None
        equity_prev_denom = self._amount(bal_prev_denom, "TOT_SHARE_EQUITY_EXCL_MIN_INT") if bal_prev_denom else None

        avg_assets = self._avg(total_assets, total_assets_prev_denom)
        avg_equity = self._avg(equity, equity_prev_denom)

        net_margin = self._ratio(net_profit, revenue)
        asset_turnover = self._ratio(revenue, avg_assets)
        equity_multiplier = self._ratio(avg_assets, avg_equity)
        debt_ratio = self._ratio(total_liab, total_assets)
        roa = self._ratio(net_profit, avg_assets)
        roe = self._ratio(net_profit, avg_equity)

        return {
            "net_profit": net_profit,
            "revenue": revenue,
            "total_assets": total_assets,
            "total_liab": total_liab,
            "total_equity": equity,
            "avg_assets": avg_assets,
            "avg_equity": avg_equity,
            "net_margin": net_margin,
            "asset_turnover": asset_turnover,
            "equity_multiplier": equity_multiplier,
            "debt_ratio": debt_ratio,
            "roa": roa,
            "roe": roe,
        }

    def _get_net_profit(
        self,
        period_kind: str,
        inc_cur: Optional[Dict[str, Any]],
        inc_prev_period: Optional[Dict[str, Any]],
    ) -> Optional[float]:
        if period_kind == "single_quarter":
            cur = self._amount(inc_cur, "NET_PRO_EXCL_MIN_INT_INC")
            prev = self._amount(inc_prev_period, "NET_PRO_EXCL_MIN_INT_INC") if inc_prev_period else None
            if cur is not None and prev is not None:
                return cur - prev
            return cur
        return self._amount(inc_cur, "NET_PRO_EXCL_MIN_INT_INC")

    def _get_revenue(
        self,
        period_kind: str,
        inc_cur: Optional[Dict[str, Any]],
        inc_prev_period: Optional[Dict[str, Any]],
    ) -> Optional[float]:
        if period_kind == "single_quarter":
            cur = self._amount(inc_cur, "TOT_OPERA_REV")
            prev = self._amount(inc_prev_period, "TOT_OPERA_REV") if inc_prev_period else None
            if cur is not None and prev is not None:
                return cur - prev
            return cur
        return self._amount(inc_cur, "TOT_OPERA_REV")

    @staticmethod
    def _find_rt_by_period(
        period_map: Dict[Tuple[int, str], Dict[str, Any]],
        target_period: str,
    ) -> Optional[str]:
        for (_, rt), r in period_map.items():
            if r.get("reporting_period") == target_period:
                return rt
        return None

    def _extrapolate_q3_full_year(
        self,
        base: Dict[str, Any],
        ctx: Dict[str, Any],
        *,
        inc_map: Dict[Tuple[int, str], Dict[str, Any]],
        bal_map: Dict[Tuple[int, str], Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Extrapolate Q3 YTD to full year: profit/revenue × 4/3; balance avg unchanged.

        `base` is the already-built YTD response (carries meta like symbol/
        source/report_type). `ctx` carries the intermediate rows/ratios
        (inc_cur/bal_cur/cur/prev) that are NOT part of the HTTP response.

        The extrapolated view is a full-year FORECAST, so its prior-period
        baseline must also be a full year — the prior year's annual (年报)
        actuals — NOT the prior-year Q3 YTD that the underlying YTD response
        uses. Comparing a forecast full year to a prior Q3 YTD would
        systematically inflate every delta/direction. If the prior year annual
        is unavailable, prev is left None rather than emitting a false trend.
        """
        scaled_cur = dict(ctx["cur"])
        # Scale profit and revenue:
        if scaled_cur.get("net_profit") is not None:
            scaled_cur["net_profit"] = scaled_cur["net_profit"] * 4 / 3
        if scaled_cur.get("revenue") is not None:
            scaled_cur["revenue"] = scaled_cur["revenue"] * 4 / 3
        # Recompute ratios:
        net_profit = scaled_cur.get("net_profit")
        revenue = scaled_cur.get("revenue")
        avg_assets = scaled_cur.get("avg_assets")
        avg_equity = scaled_cur.get("avg_equity")
        total_assets = scaled_cur.get("total_assets")
        total_liab = scaled_cur.get("total_liab")
        scaled_cur["net_margin"] = self._ratio(net_profit, revenue)
        scaled_cur["asset_turnover"] = self._ratio(revenue, avg_assets)
        scaled_cur["equity_multiplier"] = self._ratio(avg_assets, avg_equity)
        scaled_cur["debt_ratio"] = self._ratio(total_liab, total_assets)
        scaled_cur["roa"] = self._ratio(net_profit, avg_assets)
        scaled_cur["roe"] = self._ratio(net_profit, avg_equity)

        # Scale the income row to the same 4/3 caliber so the detail stacks /
        # equations stay consistent with the scaled ratios.
        scaled_inc = self._scale_income_row(ctx.get("inc_cur"), 4 / 3)

        # Prior-period baseline = prior year ANNUAL (full-year actual), so the
        # forecast-vs-actual comparison is full-year vs full-year. Falls back to
        # None when prior-year annual data is missing (no false trend).
        target_year, _ = self._year_and_month(base["target_reporting_period"])
        prior_annual_period = f"{target_year - 1}-12-31"
        ext_prev, _, _ = self._ratios_for(
            period_kind="annual", target_period=prior_annual_period,
            inc_map=inc_map, bal_map=bal_map,
        )
        ext_prev_period = prior_annual_period if ext_prev else None

        # Rebuild response with scaled cur + scaled income row; balance sheet
        # average is unchanged.
        return self._build_dupont_response(
            period_kind="ytd", target_reporting_period=base["target_reporting_period"],
            symbol=base["symbol"], source=base["source"], market=base["market"],
            report_type=base["report_type"], statement_code=base["statement_code"],
            inc_cur=scaled_inc, bal_cur=ctx.get("bal_cur"),
            cur=scaled_cur, prev=ext_prev,
            prev_period=ext_prev_period,
            is_extrapolated=True,
        )

    def _build_dupont_response(
        self,
        *,
        period_kind: Literal["annual", "single_quarter", "ytd", "ttm"],
        target_reporting_period: str,
        symbol: str,
        source: str,
        market: str,
        report_type: str,
        statement_code: str,
        inc_cur: Optional[Dict[str, Any]],
        bal_cur: Optional[Dict[str, Any]],
        cur: Dict[str, Optional[float]],
        prev: Optional[Dict[str, Optional[float]]] = None,
        prev_period: Optional[str] = None,
        is_extrapolated: bool = False,
    ) -> Dict[str, Any]:
        period = bal_cur.get("reporting_period") if bal_cur else inc_cur.get("reporting_period") if inc_cur else target_reporting_period
        security_name = (bal_cur.get("security_name") if bal_cur else inc_cur.get("security_name")) if (inc_cur or bal_cur) else None

        # Period-specific notes (also surfaced in the frontend calc-notes panel).
        # The balance-sheet denominator endpoints differ by kind:
        #   annual / ytd / ttm → (本期末, 上年末 12-31) 平均
        #   single_quarter     → (本期末, 同年上一报告期季末) 平均
        # Note: TTM asset average uses last year-end rather than the prior-year
        # same-period snapshot — a simplified denominator that keeps the DuPont
        # identity exact (avg_assets / avg_equity share the same pair).
        kind_notes = {
            "annual": "年度口径：净利润取全年累计；资产/权益用(本期末, 上年末)平均",
            "single_quarter": "单季度口径：净利润取当季累计减上季累计；资产/权益用(本期末, 同年上一季末)平均",
            "ytd": "年初至今累计口径：净利润取年初至今累计；资产/权益用(本期末, 上年末)平均",
            "ttm": "滚动12个月(TTM)口径：净利润取当前累计加上年全年减上年同期累计；资产/权益用(本期末, 上年末)平均(简化口径)",
        }

        # Decomposition tree
        net_margin_node = BIDupontTreeNode(
            **self._metric_node(
                code="net_margin", label="销售净利率",
                value=cur.get("net_margin"), prev_value=prev.get("net_margin") if prev else None,
            ).model_dump(),
            children=[
                BIDupontTreeNode(**self._metric_node(
                    code="net_profit", label="净利润",
                    value=cur.get("net_profit"), prev_value=prev.get("net_profit") if prev else None,
                    unit="amount_yuan",
                ).model_dump()),
                BIDupontTreeNode(**self._metric_node(
                    code="revenue", label="营业收入",
                    value=cur.get("revenue"), prev_value=prev.get("revenue") if prev else None,
                    unit="amount_yuan",
                ).model_dump()),
            ],
        )
        asset_turnover_node = BIDupontTreeNode(
            **self._metric_node(
                code="asset_turnover", label="总资产周转率",
                value=cur.get("asset_turnover"), prev_value=prev.get("asset_turnover") if prev else None,
            ).model_dump(),
            children=[
                BIDupontTreeNode(**self._metric_node(
                    code="turnover_revenue", label="营业收入",
                    value=cur.get("revenue"), prev_value=prev.get("revenue") if prev else None,
                    unit="amount_yuan",
                ).model_dump()),
                BIDupontTreeNode(**self._metric_node(
                    code="total_assets", label="资产总额",
                    value=cur.get("avg_assets"), prev_value=prev.get("avg_assets") if prev else None,
                    unit="amount_yuan", note="期初期末平均",
                ).model_dump()),
            ],
        )
        debt_ratio_node = BIDupontTreeNode(
            **self._metric_node(
                code="debt_ratio", label="资产负债率",
                value=cur.get("debt_ratio"), prev_value=prev.get("debt_ratio") if prev else None,
            ).model_dump(),
            children=[
                BIDupontTreeNode(**self._metric_node(
                    code="total_liabilities", label="负债总额",
                    value=cur.get("total_liab"), prev_value=prev.get("total_liab") if prev else None,
                    unit="amount_yuan",
                ).model_dump()),
                BIDupontTreeNode(**self._metric_node(
                    code="total_assets_right", label="资产总额",
                    value=cur.get("total_assets"), prev_value=prev.get("total_assets") if prev else None,
                    unit="amount_yuan",
                ).model_dump()),
            ],
        )
        equity_multiplier_node = BIDupontTreeNode(
            **self._metric_node(
                code="equity_multiplier", label="权益乘数",
                value=cur.get("equity_multiplier"), prev_value=prev.get("equity_multiplier") if prev else None,
                note="1 / (1 - 资产负债率)",
            ).model_dump(),
            children=[debt_ratio_node],
        )
        roe_node = BIDupontTreeNode(
            **self._metric_node(
                code="roe", label="净资产收益率",
                value=cur.get("roe"), prev_value=prev.get("roe") if prev else None,
            ).model_dump(),
            children=[
                net_margin_node,
                asset_turnover_node,
                equity_multiplier_node,
            ],
        )

        # Flat node map
        flat_nodes: Dict[str, Dict[str, Any]] = {}
        for node in (
            roe_node,
            BIDupontTreeNode(**self._metric_node(
                code="roa", label="总资产利润率",
                value=cur.get("roa"), prev_value=prev.get("roa") if prev else None,
            ).model_dump()),
            equity_multiplier_node,
            net_margin_node,
            asset_turnover_node,
            debt_ratio_node,
            net_margin_node.children[0],
            net_margin_node.children[1],
            asset_turnover_node.children[0],
            asset_turnover_node.children[1],
            debt_ratio_node.children[0],
            debt_ratio_node.children[1],
        ):
            flat_nodes[node.code] = node.model_dump()

        # Headline drivers
        headline_drivers = [
            BIDriverItem(
                label="ROE", value=cur.get("roe"), prev_value=prev.get("roe") if prev else None,
                note=self._driver_note("净资产收益率", cur.get("roe"), prev.get("roe") if prev else None),
                direction=self._delta_direction(
                    cur.get("roe") - prev.get("roe") if (cur.get("roe") is not None and prev and prev.get("roe") is not None) else None
                ),
            ),
            BIDriverItem(
                label="销售净利率", value=cur.get("net_margin"), prev_value=prev.get("net_margin") if prev else None,
                note=self._driver_note("销售净利率", cur.get("net_margin"), prev.get("net_margin") if prev else None),
                direction=self._delta_direction(
                    cur.get("net_margin") - prev.get("net_margin") if (cur.get("net_margin") is not None and prev and prev.get("net_margin") is not None) else None
                ),
            ),
            BIDriverItem(
                label="总资产周转率", value=cur.get("asset_turnover"), prev_value=prev.get("asset_turnover") if prev else None,
                note=self._driver_note("总资产周转率", cur.get("asset_turnover"), prev.get("asset_turnover") if prev else None),
                direction=self._delta_direction(
                    cur.get("asset_turnover") - prev.get("asset_turnover") if (cur.get("asset_turnover") is not None and prev and prev.get("asset_turnover") is not None) else None
                ),
            ),
            BIDriverItem(
                label="资产负债率", value=cur.get("debt_ratio"), prev_value=prev.get("debt_ratio") if prev else None,
                note=self._driver_note("资产负债率", cur.get("debt_ratio"), prev.get("debt_ratio") if prev else None),
                direction=self._delta_direction(
                    cur.get("debt_ratio") - prev.get("debt_ratio") if (cur.get("debt_ratio") is not None and prev and prev.get("debt_ratio") is not None) else None
                ),
            ),
        ]

        # Detail equations/stacks: reuse same logic regardless of period_kind (uses cur inc_cur/bal_cur)
        inc_source = inc_cur if inc_cur else None
        bal_source = bal_cur if bal_cur else None
        period_expense = self._sum(inc_source, ["LESS_SELLING_EXP", "LESS_ADMIN_EXP", "LESS_FIN_EXP", "RD_EXP"])
        cost_total = self._sum(inc_source, ["LESS_OPERA_COST", "LESS_BUS_TAX_SURCHARGE"]) + (period_expense or 0) + (self._amount(inc_source, "LESS_ASSETS_IMPAIR_LOSS") or 0)
        cur_assets = self._amount(bal_source, "TOTAL_CUR_ASSETS")
        noncur_assets = self._amount(bal_source, "TOT_NONCUR_ASSETS")
        detail_equations = [
            BIDetailEquation(
                result_label="净利润", result_value=cur.get("net_profit"),
                expression=f"营业总收入 - 成本总额",
                note="销售净利率的利润端来源", unit="amount_yuan",
            ),
            BIDetailEquation(
                result_label="成本总额", result_value=cost_total,
                expression="营业成本 + 税金及附加 + 期间费用 + 资产减值损失",
                note="用于解释净利润被哪些成本项消耗", unit="amount_yuan",
            ),
            BIDetailEquation(
                result_label="资产总额", result_value=cur.get("total_assets"),
                expression=f"流动资产 + 非流动资产",
                note="总资产周转率与资产负债率共用的分母", unit="amount_yuan",
            ),
            BIDetailEquation(
                result_label="资产负债率", result_value=cur.get("debt_ratio"),
                expression="负债总额 / 资产总额",
                note="权益乘数由 1 / (1 - 资产负债率) 推导", unit="ratio",
            ),
        ]

        # Breakdown stacks
        detail_stacks = []
        if inc_source:
            detail_stacks.append(self._build_stack(
                title="收入总额", accent="#1684f5", row=inc_source,
                items=[
                    ("营业总收入", "TOT_OPERA_REV"),
                    ("投资收益", "PLUS_NET_INV_INC"),
                    ("公允价值变动收益", "PLUS_NET_GAIN_CHG_FV"),
                    ("资产处置收益", "GAIN_DISPOSAL_ASSETS"),
                    ("其他收益", "OTH_INCOME"),
                ],
                total=cur.get("revenue"),
            ))
            detail_stacks.append(self._build_stack(
                title="成本总额", accent="#e05260", row=inc_source,
                items=[
                    ("营业成本", "LESS_OPERA_COST"),
                    ("税金及附加", "LESS_BUS_TAX_SURCHARGE"),
                    ("期间费用", "__period_expense__"),
                    ("资产减值损失", "LESS_ASSETS_IMPAIR_LOSS"),
                ],
                total=cost_total,
                overrides={"__period_expense__": period_expense},
            ))
            detail_stacks.append(self._build_stack(
                title="期间费用", accent="#f0a532", row=inc_source,
                items=[
                    ("销售费用", "LESS_SELLING_EXP"),
                    ("管理费用", "LESS_ADMIN_EXP"),
                    ("研发费用", "RD_EXP"),
                    ("财务费用", "LESS_FIN_EXP"),
                ],
                total=period_expense,
            ))
        if bal_source:
            detail_stacks.append(self._build_stack(
                title="流动资产", accent="#16a765", row=bal_source,
                items=[
                    ("货币资金", "CURRENCY_CAP"),
                    ("应收账款", "ACCT_RECEIVABLE"),
                    ("预付款项", "PREPAYMENT"),
                    ("存货", "INV"),
                ],
                total=cur_assets,
            ))
            detail_stacks.append(self._build_stack(
                title="非流动资产", accent="#7c5cc4", row=bal_source,
                items=[
                    ("长期股权投资", "LT_EQUITY_INV"),
                    ("固定资产", "FIXED_ASSETS"),
                    ("无形资产", "INTANGIBLE_ASSETS"),
                    ("商誉", "GOODWILL"),
                    ("递延所得税资产", "DEFERRED_TAX_ASSETS"),
                ],
                total=noncur_assets,
            ))
            detail_stacks.append(self._build_stack(
                title="负债构成", accent="#5b6f86", row=bal_source,
                items=[
                    ("短期借款", "ST_BORROWING"),
                    ("应付账款", "ACCT_PAYABLE"),
                    ("预收款项", "ADV_RECEIPT"),
                    ("长期借款", "LT_LOAN"),
                    ("租赁负债", "LEASE_LIABILITY"),
                ],
                total=cur.get("total_liab"),
            ))

        notes: List[str] = []
        notes.append(kind_notes.get(period_kind, ""))
        if is_extrapolated:
            notes.append("Q3外推：按Q3YTD×4/3线性外推全年预测；趋势对比基准为上年年报全年实际（非上年三季报累计）")
        notes.append("资产负债表项目按期初期末平均计算；利润表项目取本期值")

        result = BIDupontResponse(
            generated_at=datetime.now().astimezone().isoformat(),
            symbol=symbol, source=source, market=market,
            report_type=report_type, statement_code=statement_code,
            period=period, prev_period=prev_period, security_name=security_name,
            period_kind=period_kind, target_reporting_period=target_reporting_period,
            headline_drivers=headline_drivers,
            tree=roe_node, nodes=flat_nodes,
            detail_equations=detail_equations, detail_stacks=detail_stacks,
            notes=notes,
        ).model_dump()
        return result

    @classmethod
    def _metric_node(
        cls,
        *,
        code: str,
        label: str,
        value: Optional[float],
        prev_value: Optional[float],
        unit: str = "ratio",
        note: Optional[str] = None,
    ) -> BIDupontMetricNode:
        delta = None
        if value is not None and prev_value is not None:
            delta = value - prev_value
        return BIDupontMetricNode(
            code=code, label=label, value=value, prev_value=prev_value,
            delta=delta, direction=cls._delta_direction(delta),
            unit=unit, available=value is not None, note=note,
        )

    @classmethod
    def _driver_note(cls, label: str, cur: Optional[float], prev: Optional[float]) -> str:
        if cur is None:
            return f"{label}数据缺失"
        if prev is None:
            return f"{label}本期可用，上期不可比"
        delta = cur - prev
        sign = "提升" if delta > 0 else "下降" if delta < 0 else "持平"
        return f"{label}较上期{sign}"

    @classmethod
    def _build_stack(
        cls,
        *,
        title: str,
        accent: str,
        row: Dict[str, Any],
        items: List[Tuple[str, str]],
        total: Optional[float],
        overrides: Optional[Dict[str, float]] = None,
    ) -> BIDetailStack:
        overrides = overrides or {}
        rows: List[BIDetailStackRow] = []
        for label, field in items:
            value = overrides[field] if field in overrides else cls._amount(row, field)
            rows.append(BIDetailStackRow(label=label, raw_field=field, value=value))
        return BIDetailStack(title=title, total=total, accent=accent, rows=rows)

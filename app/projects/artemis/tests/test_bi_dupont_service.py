"""Tests for BISimpleService.get_dupont_analysis (new BI layer).

Covers the caliber-consistency fixes:
- single_quarter: detail stacks/equations must use a single-quarter income
  row (YTD − prior YTD), not the raw YTD row.
- ytd + Q3 extrapolation: detail stacks must scale with the 4/3 factor.
- internal intermediate rows must NOT leak into the HTTP response.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from artemis.services.bi_simple_service import BISimpleService


# Synthetic cumulative-YTD income rows (yuan) for 000021, 2024 + 2025.
INCOME_ROWS: List[Dict[str, Any]] = [
    # 2025
    {"reporting_period": "2025-03-31", "report_type": "1", "security_name": "深科技",
     "TOT_OPERA_REV": "100", "NET_PRO_EXCL_MIN_INT_INC": "10", "LESS_OPERA_COST": "60"},
    {"reporting_period": "2025-06-30", "report_type": "2", "security_name": "深科技",
     "TOT_OPERA_REV": "300", "NET_PRO_EXCL_MIN_INT_INC": "30", "LESS_OPERA_COST": "180"},
    {"reporting_period": "2025-09-30", "report_type": "3", "security_name": "深科技",
     "TOT_OPERA_REV": "600", "NET_PRO_EXCL_MIN_INT_INC": "60", "LESS_OPERA_COST": "360"},
    {"reporting_period": "2025-12-31", "report_type": "4", "security_name": "深科技",
     "TOT_OPERA_REV": "1000", "NET_PRO_EXCL_MIN_INT_INC": "100", "LESS_OPERA_COST": "600"},
    # 2024
    {"reporting_period": "2024-03-31", "report_type": "1", "security_name": "深科技",
     "TOT_OPERA_REV": "80", "NET_PRO_EXCL_MIN_INT_INC": "8", "LESS_OPERA_COST": "48"},
    {"reporting_period": "2024-06-30", "report_type": "2", "security_name": "深科技",
     "TOT_OPERA_REV": "240", "NET_PRO_EXCL_MIN_INT_INC": "24", "LESS_OPERA_COST": "144"},
    {"reporting_period": "2024-09-30", "report_type": "3", "security_name": "深科技",
     "TOT_OPERA_REV": "480", "NET_PRO_EXCL_MIN_INT_INC": "48", "LESS_OPERA_COST": "288"},
    {"reporting_period": "2024-12-31", "report_type": "4", "security_name": "深科技",
     "TOT_OPERA_REV": "900", "NET_PRO_EXCL_MIN_INT_INC": "90", "LESS_OPERA_COST": "540"},
]

# Period-end balance snapshots (yuan).
BALANCE_ROWS: List[Dict[str, Any]] = [
    {"reporting_period": "2025-03-31", "report_type": "1", "security_name": "深科技",
     "TOTAL_ASSETS": "5000", "TOTAL_LIAB": "2000", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "3000"},
    {"reporting_period": "2025-06-30", "report_type": "2", "security_name": "深科技",
     "TOTAL_ASSETS": "5200", "TOTAL_LIAB": "2000", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "3200"},
    {"reporting_period": "2025-09-30", "report_type": "3", "security_name": "深科技",
     "TOTAL_ASSETS": "6000", "TOTAL_LIAB": "2200", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "3800"},
    {"reporting_period": "2025-12-31", "report_type": "4", "security_name": "深科技",
     "TOTAL_ASSETS": "6500", "TOTAL_LIAB": "2300", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "4200"},
    {"reporting_period": "2024-03-31", "report_type": "1", "security_name": "深科技",
     "TOTAL_ASSETS": "4600", "TOTAL_LIAB": "1850", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "2750"},
    {"reporting_period": "2024-06-30", "report_type": "2", "security_name": "深科技",
     "TOTAL_ASSETS": "4700", "TOTAL_LIAB": "1870", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "2830"},
    {"reporting_period": "2024-09-30", "report_type": "3", "security_name": "深科技",
     "TOTAL_ASSETS": "4800", "TOTAL_LIAB": "1900", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "2900"},
    {"reporting_period": "2024-12-31", "report_type": "4", "security_name": "深科技",
     "TOTAL_ASSETS": "4900", "TOTAL_LIAB": "1950", "TOT_SHARE_EQUITY_EXCL_MIN_INT": "2950"},
]


def _make_service() -> BISimpleService:
    svc = BISimpleService()

    def fake_query_financial(self, *, source, statement_type, **kwargs):
        rows = INCOME_ROWS if statement_type == "income" else BALANCE_ROWS
        return {"rows": [dict(r) for r in rows]}

    # monkeypatch the instance method (and the class-level lookup used by
    # _fetch_all_dupont_rows, which calls self.query_financial).
    svc.query_financial = fake_query_financial.__get__(svc, BISimpleService)  # type: ignore[method-assign]
    return svc


def _stack(resp: Dict[str, Any], title: str) -> Dict[str, Any]:
    for s in resp["detail_stacks"]:
        if s["title"] == title:
            return s
    raise AssertionError(f"stack {title!r} not found")


def _equation(resp: Dict[str, Any], result_label: str) -> Dict[str, Any]:
    for e in resp["detail_equations"]:
        if e["result_label"] == result_label:
            return e
    raise AssertionError(f"equation {result_label!r} not found")


def _approx(a, b, tol=1e-6):
    assert a is not None and b is not None, f"None encountered: {a!r} vs {b!r}"
    assert math.isclose(a, b, rel_tol=0, abs_tol=tol), f"{a} != {b}"


def test_single_quarter_detail_uses_single_quarter_caliber():
    """single_quarter: detail stacks must be on single-quarter (YTD−prior YTD) caliber."""
    svc = _make_service()
    resp = svc.get_dupont_analysis(
        symbol="000021", source="amazing_data",
        period_kind="single_quarter", target_reporting_period="2025-06-30",
    )

    # Ratios are single-quarter: Q2 YTD − Q1 YTD.
    _approx(resp["nodes"]["net_profit"]["value"], 30 - 10)      # 20
    _approx(resp["nodes"]["revenue"]["value"], 300 - 100)       # 200

    # The "收入总额" breakdown stack total and its 营业总收入 row must both be
    # the single-quarter revenue (200), NOT the YTD value (300). Before the
    # fix the row read from the raw YTD row (300) while the total was 200.
    rev_stack = _stack(resp, "收入总额")
    _approx(rev_stack["total"], 200)
    _approx(rev_stack["rows"][0]["value"], 200)

    # Cost stack: single-quarter 营业成本 = 180 − 60 = 120, matching its total.
    cost_stack = _stack(resp, "成本总额")
    _approx(cost_stack["total"], 120)
    _approx(cost_stack["rows"][0]["value"], 120)

    # The 净利润 equation result must equal the single-quarter net profit.
    np_eq = _equation(resp, "净利润")
    _approx(np_eq["result_value"], 20)

    # DuPont identity holds.
    cur = resp["tree"]
    _approx(cur["value"],
            cur["children"][0]["value"] * cur["children"][1]["value"] * cur["children"][2]["value"])

    # Internal rows must not leak into the HTTP response.
    for key in ("_inc_cur", "_bal_cur", "_cur", "_prev"):
        assert key not in resp, f"internal key {key!r} leaked into response"


def test_ytd_q3_extrapolation_scales_detail_stacks():
    """ytd + Q3 extrapolation: detail stacks must scale by 4/3 with the ratios."""
    svc = _make_service()
    resp = svc.get_dupont_analysis(
        symbol="000021", source="amazing_data",
        period_kind="ytd", target_reporting_period="2025-09-30",
        extrapolate_q4=True,
    )

    ext = resp["extrapolated_full_year"]
    assert ext is not None

    # YTD revenue 600 → ×4/3 = 800; net profit 60 → 80.
    _approx(ext["nodes"]["revenue"]["value"], 600 * 4 / 3)
    _approx(ext["nodes"]["net_profit"]["value"], 60 * 4 / 3)

    # Detail stack 营业总收入 row and total must both be scaled (800), not the
    # raw YTD 600. Before the fix the row stayed at 600 while the total was 800.
    rev_stack = _stack(ext, "收入总额")
    _approx(rev_stack["total"], 800)
    _approx(rev_stack["rows"][0]["value"], 800)

    # Cost stack scales too: 360 × 4/3 = 480.
    cost_stack = _stack(ext, "成本总额")
    _approx(cost_stack["total"], 360 * 4 / 3)
    _approx(cost_stack["rows"][0]["value"], 360 * 4 / 3)

    # Balance-sheet-driven ratios unchanged (avg assets/equity same as YTD).
    _approx(ext["nodes"]["debt_ratio"]["value"], resp["nodes"]["debt_ratio"]["value"])

    # DuPont identity holds on the extrapolated tree.
    cur = ext["tree"]
    _approx(cur["value"],
            cur["children"][0]["value"] * cur["children"][1]["value"] * cur["children"][2]["value"])

    # P1 regression: the extrapolated view is a full-year FORECAST, so its
    # prior-period baseline must be the prior year ANNUAL (full-year actual),
    # NOT the prior-year Q3 YTD that the underlying YTD response uses.
    # Prior-year annual (2024-12-31): net_profit 90, equity avg 2950 (no 2023
    # data → single-endpoint fallback) → roe = 90/2950.
    # Prior-year Q3 YTD (the old buggy baseline): net_profit 48, equity 2900
    # → roe = 48/2900. These differ, so the assertion discriminates.
    prior_annual_roe = 90 / 2950
    prior_q3_ytd_roe = 48 / 2900
    ext_roe_prev = ext["nodes"]["roe"]["prev_value"]
    assert ext_roe_prev is not None
    _approx(ext_roe_prev, prior_annual_roe)
    assert not math.isclose(ext_roe_prev, prior_q3_ytd_roe, abs_tol=1e-6), \
        "extrapolated prev must not be the prior-year Q3 YTD baseline"
    # prev_period reflects the annual baseline, not the Q3 YTD one.
    assert ext["prev_period"] == "2024-12-31"

    for key in ("_inc_cur", "_bal_cur", "_cur", "_prev"):
        assert key not in ext, f"internal key {key!r} leaked into extrapolated response"


def test_prev_period_is_populated():
    """prev_period must be carried into the response (was always None before)."""
    svc = _make_service()
    resp = svc.get_dupont_analysis(
        symbol="000021", source="amazing_data",
        period_kind="ytd", target_reporting_period="2025-09-30",
    )
    # ytd → 同比 → prior year same period.
    assert resp["prev_period"] == "2024-09-30"


def test_statement_code_is_passed_through():
    """statement_code must reflect the caller's value, not be hardcoded to '1'.

    The fetch uses the passed statement_code; the response metadata must agree
    so a 母公司 (6) query isn't mislabeled as 合并 (1).
    """
    svc = _make_service()
    resp = svc.get_dupont_analysis(
        symbol="000021", source="amazing_data",
        statement_code="6",
        period_kind="ytd", target_reporting_period="2025-09-30",
    )
    assert resp["statement_code"] == "6"

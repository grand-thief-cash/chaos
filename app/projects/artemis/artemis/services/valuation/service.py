from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping

import pandas as pd

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.log.logger import get_logger
from artemis.models.valuation import ValuationAnalyzeRequest, ValuationHistoryRequest
from artemis.services.valuation.calculations import (
    DEFAULT_WEIGHTS,
    SCENARIOS,
    combine_method_prices,
    confidence_score,
    dcf_analysis,
    ev_ebitda_analysis,
    forward_growth_rates,
    forward_pe_prices,
    multiple_band,
    number,
    pb_roe_prices,
)


logger = get_logger("valuation.service")
VALUATION_SOURCE = "eastmoney_valuation"
CONSENSUS_SOURCES = ("ths_consensus", "eastmoney_consensus")
SCENARIO_DEFINITIONS = {
    "bear": {
        "label": "低一致预期",
        "semantics": "low_consensus",
        "tail_stress": False,
        "description": "机构预测分布低位 × 历史倍数低位；仍不代表增长逻辑被证伪。",
    },
    "base": {
        "label": "中位一致预期",
        "semantics": "base_consensus",
        "tail_stress": False,
        "description": "机构预测均值/中位附近 × 历史倍数中位。",
    },
    "bull": {
        "label": "高一致预期",
        "semantics": "high_consensus",
        "tail_stress": False,
        "description": "机构预测分布高位 × 历史倍数高位；属于双重乐观组合。",
    },
}

INCOME_FIELDS = [
    "reporting_period", "report_type", "ann_date", "actual_ann_date",
    "security_name", "NET_PRO_EXCL_MIN_INT_INC", "TOT_OPERA_REV",
    "EBIT", "EBITDA",
]
BALANCE_FIELDS = [
    "reporting_period", "report_type", "ann_date", "actual_ann_date",
    "security_name", "TOT_SHARE_EQUITY_EXCL_MIN_INT", "TOT_SHARE",
    "CAP_STOCK", "CURRENCY_CAP", "TRADING_FINASSETS", "ST_BORROWING",
    "LT_LOAN", "BONDS_PAYABLE", "LEASE_LIABILITY",
    "NONCUR_LIAB_DUE_WITHIN_1Y", "TOTAL_ASSETS", "TOTAL_LIAB",
]
CASHFLOW_FIELDS = [
    "reporting_period", "report_type", "ann_date", "actual_ann_date",
    "security_name", "NET_CASH_FLOWS_OPERA_ACT",
    "CASH_PAID_PUR_CONST_FIOLTA", "FREE_CASH_FLOW",
]


class ValuationDataError(ValueError):
    pass


def _client() -> PhoenixAClient:
    dept = cfg_mgr.get_dept_services_for_source(None)
    if not dept or not dept.phoenixA:
        raise ValuationDataError("phoenixA service not configured")
    config = dept.phoenixA
    return PhoenixAClient(
        host=config.host,
        port=config.port,
        logger=logger,
        timeout_seconds=getattr(config, "timeout_seconds", 30),
    )


def _iso(value: date | str | None) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")[:10]


def _next_day(value: str) -> str:
    return (pd.Timestamp(value) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("rows") or payload.get("data") or []
    if not isinstance(rows, list):
        return []
    result: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("top_level"), dict):
            merged = dict(row["top_level"])
            if isinstance(row.get("data_json"), dict):
                merged.update(row["data_json"])
            result.append(merged)
        else:
            result.append(row)
    return result


def _query_financial(
    client: PhoenixAClient,
    *,
    security_id: int,
    source: str,
    statement_type: str,
    statement_code: str,
    valuation_date: str,
    fields: List[str],
) -> List[Dict[str, Any]]:
    path = f"/api/v2/financial/{source}/{statement_type}"
    page = 1
    page_size = 200
    rows: List[Dict[str, Any]] = []
    while True:
        params = {
            "security_id": str(security_id),
            "statement_code": statement_code,
            "ann_date_before": _next_day(valuation_date),
            "period_end": valuation_date,
            "fields": ",".join(fields),
            "format": "flat",
            "page": str(page),
            "page_size": str(page_size),
        }
        response = client.get(path, params)
        if not 200 <= response.status_code < 300:
            raise ValuationDataError(
                f"financial query failed for {statement_type}: {response.status_code}"
            )
        payload = response.json()
        page_rows = _rows_from_payload(payload)
        rows.extend(page_rows)
        total = payload.get("total") if isinstance(payload, dict) else None
        if len(page_rows) < page_size or (total is not None and len(rows) >= int(total)):
            break
        page += 1
        if page > 20:
            break
    return sorted(
        rows,
        key=lambda row: str(row.get("reporting_period") or ""),
        reverse=True,
    )


def _period_map(rows: Iterable[Mapping[str, Any]]) -> Dict[tuple[int, str], Dict[str, Any]]:
    result: Dict[tuple[int, str], Dict[str, Any]] = {}
    for row in rows:
        period = str(row.get("reporting_period") or "")
        report_type = str(row.get("report_type") or "")
        if len(period) >= 4 and period[:4].isdigit() and report_type:
            result[(int(period[:4]), report_type)] = dict(row)
    return result


def _ttm_value(rows: List[Dict[str, Any]], field: str) -> float | None:
    if not rows:
        return None
    latest = rows[0]
    current = number(latest.get(field))
    period = str(latest.get("reporting_period") or "")
    report_type = str(latest.get("report_type") or "")
    if current is None or len(period) < 4 or not period[:4].isdigit():
        return current
    if report_type == "4":
        return current
    year = int(period[:4])
    rows_by_period = _period_map(rows)
    prior_annual = number((rows_by_period.get((year - 1, "4")) or {}).get(field))
    prior_ytd = number((rows_by_period.get((year - 1, report_type)) or {}).get(field))
    if prior_annual is None or prior_ytd is None:
        return current
    return current + prior_annual - prior_ytd


def _latest_balance_value(rows: List[Dict[str, Any]], *fields: str) -> float | None:
    if not rows:
        return None
    for field in fields:
        value = number(rows[0].get(field))
        if value is not None:
            return value
    return None


def _average_equity(balance_rows: List[Dict[str, Any]]) -> float | None:
    current = _latest_balance_value(balance_rows, "TOT_SHARE_EQUITY_EXCL_MIN_INT")
    if current is None or not balance_rows:
        return current
    latest = balance_rows[0]
    period = str(latest.get("reporting_period") or "")
    if len(period) < 4 or not period[:4].isdigit():
        return current
    previous = number(
        (_period_map(balance_rows).get((int(period[:4]) - 1, "4")) or {}).get(
            "TOT_SHARE_EQUITY_EXCL_MIN_INT"
        )
    )
    return current if previous is None else (current + previous) / 2


def _price_as_of(
    client: PhoenixAClient,
    security_id: int,
    valuation_date: str,
) -> Dict[str, Any] | None:
    start = (pd.Timestamp(valuation_date) - pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    bars = client.get_bars(
        asset_type="stock",
        market="zh_a",
        security_id=security_id,
        start_date=start,
        end_date=valuation_date,
        period="daily",
        adjust="nf",
        fields=["security_id", "trade_date", "symbol", "close"],
        normalize_for_cache=True,
    )
    if not bars:
        # Phase 0 valuation history already persists the vendor's unadjusted
        # close. Use it as the historical-replay fallback when canonical daily
        # bars have not yet been backfilled for that older date.
        try:
            observations = client.query_market_observations(
                source=VALUATION_SOURCE,
                security_ids=[security_id],
                start_date=start,
                end_date=valuation_date,
                observation_types=["valuation_close"],
            )
        except Exception:
            observations = []
        observations = sorted(
            observations, key=lambda item: str(item.get("trade_date") or ""),
        )
        if not observations:
            return None
        latest = observations[-1]
        close = number(latest.get("value"))
        if close is None or close <= 0:
            return None
        return {
            "date": str(latest.get("trade_date") or "")[:10],
            "close": close,
            "symbol": "",
            "price_source": VALUATION_SOURCE,
        }
    row = sorted(bars, key=lambda item: str(item.get("date") or ""))[-1]
    close = number(row.get("close"))
    if close is None or close <= 0:
        return None
    return {
        "date": str(row.get("date") or "")[:10],
        "close": close,
        "symbol": str(row.get("code") or ""),
    }


def _valuation_history(
    client: PhoenixAClient,
    security_id: int,
    valuation_date: str,
    history_years: int,
) -> Dict[str, Any]:
    start = (pd.Timestamp(valuation_date) - pd.DateOffset(years=history_years)).strftime(
        "%Y-%m-%d"
    )
    rows = client.query_market_observations(
        source=VALUATION_SOURCE,
        security_ids=[security_id],
        start_date=start,
        end_date=valuation_date,
        observation_types=["valuation_pe_ttm", "valuation_pb"],
    )
    pe = [row.get("value") for row in rows if row.get("observation_type") == "valuation_pe_ttm"]
    pb = [row.get("value") for row in rows if row.get("observation_type") == "valuation_pb"]
    return {"rows": rows, "pe": pe, "pb": pb, "start_date": start}


def _forecast_bundle_as_of(
    client: PhoenixAClient,
    security_id: int,
    valuation_date: str,
    target_year: int,
) -> Dict[str, Any] | None:
    start = (pd.Timestamp(valuation_date) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    target_types = {
        f"eps_consensus_{target_year}": "eps",
        f"bvps_consensus_{target_year}": "bvps",
        f"roe_consensus_{target_year}": "roe",
        f"cfps_consensus_{target_year}": "cash_flow_per_share",
        f"net_profit_consensus_{target_year}": "net_profit",
        f"revenue_consensus_{target_year}": "revenue",
    }
    for source in CONSENSUS_SOURCES:
        try:
            rows = client.query_market_observations(
                source=source,
                security_ids=[security_id],
                start_date=start,
                end_date=valuation_date,
            )
        except Exception as exc:
            logger.warning({"event": "valuation_consensus_query_failed", "source": source, "error": str(exc)})
            continue
        matching = [
            row for row in rows
            if str(row.get("observation_type") or "") in target_types
        ]
        if not matching:
            continue
        latest_date = max(str(row.get("trade_date") or "")[:10] for row in matching)
        latest = [
            row for row in matching
            if str(row.get("trade_date") or "")[:10] == latest_date
        ]
        observations = {
            target_types[str(row.get("observation_type"))]: row for row in latest
        }
        if "eps" in observations:
            return {
                "provider": source,
                "trade_date": latest_date,
                "fiscal_year": target_year,
                "observations": observations,
            }
    return None


def _dividend_retention_as_of(
    client: PhoenixAClient,
    *,
    security_id: int,
    valuation_date: str,
    income_rows: List[Dict[str, Any]],
    shares: float | None,
) -> Dict[str, Any] | None:
    annual_rows = [
        row for row in income_rows
        if str(row.get("report_type") or "") == "4"
        and str(row.get("reporting_period") or "")[:4].isdigit()
    ]
    if not annual_rows or not shares or shares <= 0:
        return None
    annual = sorted(
        annual_rows, key=lambda row: str(row.get("reporting_period") or ""), reverse=True,
    )[0]
    fiscal_year = str(annual.get("reporting_period"))[:4]
    annual_profit = number(annual.get("NET_PRO_EXCL_MIN_INT_INC"))
    annual_eps = annual_profit / shares if annual_profit and annual_profit > 0 else None
    if not annual_eps:
        return None
    try:
        payload = client.query_corporate_actions(
            source="amazing_data",
            action_type="dividend",
            security_id=security_id,
            period_start=f"{fiscal_year}-01-01",
            period_end=f"{fiscal_year}-12-31",
            ann_date_before=_next_day(valuation_date),
            page_size=200,
        )
    except Exception as exc:
        logger.warning({"event": "valuation_dividend_query_failed", "error": str(exc)})
        return None
    cash_dividend = 0.0
    event_count = 0
    for row in _rows_from_payload(payload):
        if str(row.get("report_period") or "")[:4] != fiscal_year:
            continue
        if str(row.get("progress_code") or "") != "3":
            continue
        cash = number(row.get("DVD_PER_SHARE_PRE_TAX_CASH"))
        if cash is not None and cash > 0:
            cash_dividend += cash
            event_count += 1
    if event_count == 0:
        return None
    payout_ratio = cash_dividend / annual_eps
    return {
        "fiscal_year": int(fiscal_year),
        "cash_dividend_per_share": cash_dividend,
        "annual_eps": annual_eps,
        "payout_ratio": payout_ratio,
        "retention_ratio": min(max(1 - payout_ratio, 0.0), 1.0),
        "event_count": event_count,
        "source": "amazing_data_dividend",
    }


def _fallback_band(center: float | None, factors: tuple[float, float, float]) -> Dict[str, float]:
    if center is None or center <= 0:
        return {}
    return dict(zip(SCENARIOS, [center * factor for factor in factors]))


def _round_prices(values: Mapping[str, Any]) -> Dict[str, float]:
    return {
        key: round(value, 2)
        for key, raw in values.items()
        if (value := number(raw)) is not None and value > 0
    }


def _round_scenario_inputs(
    values: Mapping[str, Any],
    *,
    digits: int = 4,
) -> Dict[str, float]:
    """Return the canonical operands shown to users and used for pricing."""
    return {
        key: round(value, digits)
        for key, raw in values.items()
        if (value := number(raw)) is not None and value > 0
    }


def _valuation_weights(
    *,
    raw_growth: Mapping[str, Any],
    forward_roe: float | None,
) -> tuple[Dict[str, float], str, str]:
    base_growth = number(raw_growth.get("base"))
    if (
        base_growth is not None and base_growth >= 0.20
        and forward_roe is not None and forward_roe >= 0.25
    ):
        return (
            {"forward_pe": 0.70, "pb_roe": 0.05, "ev_ebitda": 0.15, "dcf": 0.10},
            "high_growth",
            "目标年度 EPS 增长不低于 20% 且预测 ROE 不低于 25%；盈利模型主导，PB 仅作资产护栏。",
        )
    return (
        dict(DEFAULT_WEIGHTS),
        "balanced",
        "未触发高增长画像，使用均衡先验权重；不可用方法仍会在剩余方法内归一化。",
    )


def _forward_pe_sensitivity(
    *,
    eps: Mapping[str, Any],
    multiples: Mapping[str, Any],
    market_price: float,
) -> Dict[str, Any]:
    eps_values = _round_scenario_inputs(eps)
    multiple_values = _round_scenario_inputs(multiples)
    grid: Dict[str, Dict[str, float]] = {}
    candidates: List[Dict[str, Any]] = []
    for eps_scenario in SCENARIOS:
        earnings = number(eps_values.get(eps_scenario))
        if earnings is None or earnings <= 0:
            continue
        row: Dict[str, float] = {}
        for multiple_scenario in SCENARIOS:
            multiple = number(multiple_values.get(multiple_scenario))
            if multiple is None or multiple <= 0:
                continue
            value = round(earnings * multiple, 2)
            row[multiple_scenario] = value
            candidates.append({
                "eps_scenario": eps_scenario,
                "multiple_scenario": multiple_scenario,
                "price": value,
                "absolute_gap": round(value - market_price, 2),
                "gap_percent": round(value / market_price - 1, 4),
            })
        if row:
            grid[eps_scenario] = row
    if not grid:
        return {}
    nearest = min(candidates, key=lambda item: abs(item["absolute_gap"]))
    base_eps = number(eps_values.get("base"))
    base_multiple = number(multiple_values.get("base"))
    return {
        "eps": eps_values,
        "multiples": multiple_values,
        "grid": grid,
        "market_implied": {
            "market_price": round(market_price, 2),
            "forward_pe_at_base_eps": round(market_price / base_eps, 2) if base_eps else None,
            "eps_at_base_multiple": round(market_price / base_multiple, 2) if base_multiple else None,
            "nearest_grid_cell": nearest,
        },
    }


def _pe_pb_coherence(
    *,
    eps: Mapping[str, Any],
    bvps: Mapping[str, Any],
    pe: Mapping[str, Any],
    pb: Mapping[str, Any],
) -> Dict[str, Any]:
    rows: Dict[str, Dict[str, float]] = {}
    for scenario in SCENARIOS:
        earnings = number(eps.get(scenario))
        book_value = number(bvps.get(scenario))
        pe_multiple = number(pe.get(scenario))
        pb_multiple = number(pb.get(scenario))
        if not all(
            value is not None and value > 0
            for value in (earnings, book_value, pe_multiple, pb_multiple)
        ):
            continue
        implied_roe = earnings / book_value
        coherent_pb = pe_multiple * implied_roe
        gap_ratio = coherent_pb / pb_multiple
        rows[scenario] = {
            "eps": earnings,
            "bvps": book_value,
            "implied_roe": implied_roe,
            "pe": pe_multiple,
            "coherent_pb": coherent_pb,
            "observed_pb_anchor": pb_multiple,
            "pb_gap_ratio": gap_ratio,
        }
    base_gap = number((rows.get("base") or {}).get("pb_gap_ratio"))
    if base_gap is None:
        status = "unavailable"
    elif 0.75 <= base_gap <= 1.35:
        status = "aligned"
    elif 0.50 <= base_gap <= 2.00:
        status = "divergent"
    else:
        status = "severely_divergent"
    return {
        "identity": "PB = PE × (EPS / BVPS)",
        "status": status,
        "rows": rows,
        "base_gap_ratio": base_gap,
        "interpretation": (
            "PE 与 PB 倍数锚处于不同盈利/ROE 阶段；该诊断用于定位口径分歧，不能单独判定哪种方法正确。"
            if status in ("divergent", "severely_divergent")
            else "PE 与 PB 倍数锚在 Forward ROE 口径下基本一致。"
        ),
    }


def _price_reference_guide(
    *,
    headline_range: Mapping[str, Any],
    market_price: float,
    pe_sensitivity: Mapping[str, Any],
) -> Dict[str, Any]:
    low = number(headline_range.get("bear"))
    base = number(headline_range.get("base"))
    high = number(headline_range.get("bull"))
    if low is None or base is None or high is None:
        return {}
    if market_price < low:
        state = "below_low_consensus"
        label = "低于低一致预期锚"
        interpretation = "价格低于当前一致预期低位估值；先排查盈利逻辑是否已被证伪，不能仅因价格低就判断低估。"
    elif market_price < base:
        state = "between_low_and_base"
        label = "位于低位与中位预期之间"
        interpretation = "市场定价低于中位一致预期，但仍需验证目标年度盈利和倍数是否可持续。"
    elif market_price <= high:
        state = "between_base_and_high"
        label = "正在交易中高一致预期"
        interpretation = "当前价高于中位估值锚，市场正在交易更高 EPS、较高 PE，或两者的组合。"
    else:
        state = "above_high_consensus"
        label = "高于高一致预期锚"
        interpretation = "当前价格已超过矩阵高位组合，需要矩阵外的盈利上修或更高倍数才能解释。"
    return {
        "framework": "scenario_reference_not_target_price",
        "state": state,
        "state_label": label,
        "interpretation": interpretation,
        "anchors": {
            "low_consensus": round(low, 2),
            "base_consensus": round(base, 2),
            "high_consensus": round(high, 2),
            "market_price": round(market_price, 2),
        },
        "market_implied": pe_sensitivity.get("market_implied") if pe_sensitivity else None,
        "tail_stress_available": False,
        "tail_stress_note": (
            "当前低位情景仍来自机构一致预期，不是增长逻辑被证伪后的周期压力价；"
            "在中周期利润/ROE 模型完成前，不输出伪精确的尾部买入价。"
        ),
        "usage_rules": [
            "先选择自己认可的目标年度 EPS 行，再选择可持续 PE 列；不要只看对角线。",
            "将 Base 视为盈利假设锚，不把 PB/DCF 的低值直接当作买点。",
            "安全边际是用户对 Base 锚的折扣，不是模型保证；若基本面假设变化必须重新估值。",
            "当前价接近哪一格，就代表市场正在交易哪组 EPS 与 PE；投资判断的核心是验证这组假设。",
        ],
    }


def _aggregation_policy(
    *,
    weight_profile: str,
    method_prices: Mapping[str, Mapping[str, Any]],
    blended_reference: Mapping[str, Any],
) -> Dict[str, Any]:
    valid_methods = list(method_prices)
    if weight_profile == "high_growth" and "forward_pe" in method_prices:
        roles = {
            method: (
                "primary" if method == "forward_pe"
                else "guardrail" if method == "pb_roe"
                else "cross_check"
            )
            for method in valid_methods
        }
        return {
            "mode": "primary_with_cross_checks",
            "primary_method": "forward_pe",
            "headline": _round_prices(method_prices["forward_pe"]),
            "blended_reference": _round_prices(blended_reference),
            "method_roles": roles,
            "cross_check_methods": [
                method for method in valid_methods if roles[method] == "cross_check"
            ],
            "guardrail_methods": [
                method for method in valid_methods if roles[method] == "guardrail"
            ],
            "rationale": (
                "高增长画像以 Forward PE 作为主估值；DCF 与 EV/EBITDA 受逐年预测缺口影响只做交叉验证，"
                "PB 只作资产护栏。全方法加权值保留为诊断参考，不再压低主区间。"
            ),
        }
    roles = {method: "blended" for method in valid_methods}
    return {
        "mode": "weighted_blend" if len(valid_methods) > 1 else "single_method",
        "primary_method": valid_methods[0] if len(valid_methods) == 1 else None,
        "headline": _round_prices(blended_reference),
        "blended_reference": _round_prices(blended_reference),
        "method_roles": roles,
        "cross_check_methods": [],
        "guardrail_methods": [],
        "rationale": (
            "未触发高增长主模型规则；可用方法按展示权重形成主区间。"
            if len(valid_methods) > 1 else "仅一种方法可用，主区间来自该方法。"
        ),
    }


def analyze_valuation(req: ValuationAnalyzeRequest) -> Dict[str, Any]:
    client = _client()
    valuation_date = _iso(req.valuation_date or date.today())
    if valuation_date > date.today().isoformat():
        raise ValuationDataError("valuation_date cannot be in the future")
    security = client.get_security_by_id(req.security_id)
    if not security:
        raise ValuationDataError(f"security_id {req.security_id} not found")
    if security.get("asset_type") != "stock" or security.get("market") != "zh_a":
        raise ValuationDataError("valuation matrix currently supports zh_a stocks only")

    price = _price_as_of(client, req.security_id, valuation_date)
    if not price:
        raise ValuationDataError(f"no daily price on or before {valuation_date}")

    income_rows = _query_financial(
        client, security_id=req.security_id, source=req.financial_source,
        statement_type="income", statement_code=req.statement_code,
        valuation_date=valuation_date, fields=INCOME_FIELDS,
    )
    balance_rows = _query_financial(
        client, security_id=req.security_id, source=req.financial_source,
        statement_type="balance_sheet", statement_code=req.statement_code,
        valuation_date=valuation_date, fields=BALANCE_FIELDS,
    )
    cashflow_rows = _query_financial(
        client, security_id=req.security_id, source=req.financial_source,
        statement_type="cashflow", statement_code=req.statement_code,
        valuation_date=valuation_date, fields=CASHFLOW_FIELDS,
    )
    if not income_rows or not balance_rows:
        raise ValuationDataError(
            f"no point-in-time financial statements available by {valuation_date}"
        )

    ttm_profit = _ttm_value(income_rows, "NET_PRO_EXCL_MIN_INT_INC")
    ttm_revenue = _ttm_value(income_rows, "TOT_OPERA_REV")
    ttm_ebitda = _ttm_value(income_rows, "EBITDA")
    ttm_fcf = _ttm_value(cashflow_rows, "FREE_CASH_FLOW")
    shares = _latest_balance_value(balance_rows, "TOT_SHARE", "CAP_STOCK")
    equity = _latest_balance_value(balance_rows, "TOT_SHARE_EQUITY_EXCL_MIN_INT")
    cash = _latest_balance_value(balance_rows, "CURRENCY_CAP") or 0.0
    debt_fields = (
        "ST_BORROWING", "LT_LOAN", "BONDS_PAYABLE", "LEASE_LIABILITY",
        "NONCUR_LIAB_DUE_WITHIN_1Y",
    )
    debt = sum(number(balance_rows[0].get(field)) or 0.0 for field in debt_fields)
    net_debt = debt - cash
    avg_equity = _average_equity(balance_rows)
    roe = ttm_profit / avg_equity if ttm_profit is not None and avg_equity else None
    actual_eps = ttm_profit / shares if ttm_profit is not None and shares else None
    bvps = equity / shares if equity is not None and shares else None

    warnings: List[Dict[str, str]] = []
    try:
        history = _valuation_history(
            client, req.security_id, price["date"], req.history_years,
        )
    except Exception as exc:
        history = {"rows": [], "pe": [], "pb": [], "start_date": ""}
        warnings.append({"code": "VALUATION_HISTORY_UNAVAILABLE", "message": str(exc)})

    pe_band = multiple_band(history["pe"], floor=5.0, cap=100.0)
    current_pe = price["close"] / actual_eps if actual_eps and actual_eps > 0 else None
    pe_fallback = False
    if not pe_band:
        pe_band = _fallback_band(current_pe, (0.70, 1.00, 1.30))
        pe_fallback = True
        warnings.append({
            "code": "PE_HISTORY_FALLBACK",
            "message": "PE 历史快照不足，倍数带退化为当前 PE 的 70%/100%/130%。",
        })

    pb_band = multiple_band(history["pb"], floor=0.3, cap=30.0)
    current_pb = price["close"] / bvps if bvps and bvps > 0 else None
    pb_fallback = False
    if not pb_band:
        pb_band = _fallback_band(current_pb, (0.75, 1.00, 1.25))
        pb_fallback = True
        warnings.append({
            "code": "PB_HISTORY_FALLBACK",
            "message": "PB 历史快照不足，倍数带退化为当前 PB 的 75%/100%/125%。",
        })

    target_year = int(valuation_date[:4]) + req.horizon_years
    forecast = _forecast_bundle_as_of(
        client, req.security_id, valuation_date, target_year,
    )
    observations = forecast.get("observations", {}) if forecast else {}
    eps_forecast = observations.get("eps")
    has_consensus = eps_forecast is not None
    eps_extra: Dict[str, Any] = {}
    if eps_forecast:
        eps_extra = eps_forecast.get("extra_json") if isinstance(eps_forecast.get("extra_json"), dict) else {}
        mean_eps = number(eps_forecast.get("value"))
        provider_low = number(eps_extra.get("low"))
        provider_high = number(eps_extra.get("high"))
        if eps_extra.get("range_source") != "institution_detail" and mean_eps:
            provider_low = max(provider_low or mean_eps * 0.85, mean_eps * 0.85)
            provider_high = min(provider_high or mean_eps * 1.15, mean_eps * 1.15)
        eps_band = {
            "bear": provider_low or (mean_eps * 0.85 if mean_eps else None),
            "base": mean_eps,
            "bull": provider_high or (mean_eps * 1.15 if mean_eps else None),
        }
    else:
        eps_band = {}
        warnings.append({
            "code": "FORWARD_EPS_UNAVAILABLE",
            "message": f"信息截止日没有 {target_year}E EPS 快照；Forward PE 不再退化为 TTM EPS，方法已禁用。",
        })

    pricing_eps_band = _round_scenario_inputs(eps_band)
    pricing_pe_band = _round_scenario_inputs(pe_band or {})
    latest_consensus_report_date = str(eps_extra.get("latest_report_date") or "")[:10] or None
    consensus_report_age_days: int | None = None
    if latest_consensus_report_date:
        try:
            consensus_report_age_days = max(
                int((pd.Timestamp(valuation_date) - pd.Timestamp(latest_consensus_report_date)).days),
                0,
            )
        except (TypeError, ValueError):
            latest_consensus_report_date = None

    bvps_forecast = observations.get("bvps")
    roe_forecast = observations.get("roe")
    forward_bvps_base = number(bvps_forecast.get("value")) if bvps_forecast else None
    forward_roe = number(roe_forecast.get("value")) if roe_forecast else None
    forward_bvps_band = _fallback_band(forward_bvps_base, (0.95, 1.00, 1.05))
    pricing_bvps_band = _round_scenario_inputs(forward_bvps_band)
    pricing_pb_band = _round_scenario_inputs(pb_band or {})
    raw_growth, applied_growth = forward_growth_rates(
        current_value=actual_eps,
        target_values=pricing_eps_band,
        horizon_years=req.horizon_years,
    )
    dividend_retention = _dividend_retention_as_of(
        client,
        security_id=req.security_id,
        valuation_date=valuation_date,
        income_rows=income_rows,
        shares=shares,
    )

    method_prices: Dict[str, Dict[str, float]] = {}
    methods: List[Dict[str, Any]] = []
    if "forward_pe" in req.methods and pricing_pe_band and pricing_eps_band:
        values = _round_prices(forward_pe_prices(pricing_eps_band, pricing_pe_band))
        if values:
            method_prices["forward_pe"] = values
            methods.append({
                "code": "forward_pe", "label": "Forward PE", "weight": DEFAULT_WEIGHTS["forward_pe"],
                "prices": values,
                "formula": "目标价 = 目标年度 EPS × 情景 PE",
                "inputs": {
                    "eps": pricing_eps_band,
                    "pe": pricing_pe_band,
                    "target_fiscal_year": target_year,
                    "institution_count": number(eps_extra.get("institution_count")),
                    "forecast_snapshot_date": forecast.get("trade_date") if forecast else None,
                    "latest_institution_report_date": latest_consensus_report_date,
                    "latest_report_age_days": consensus_report_age_days,
                },
                "provenance": {
                    "eps_source": forecast.get("provider") if forecast else None,
                    "eps_range_source": eps_extra.get("range_source", "provider_summary"),
                    "multiple_source": "eastmoney_historical_ttm_pe_quantiles" if not pe_fallback else "current_ttm_pe_fallback",
                    "multiple_semantics": "TTM PE historical band used as forward-PE proxy",
                },
            })

    if "pb_roe" in req.methods and pricing_pb_band and pricing_bvps_band:
        values = _round_prices(pb_roe_prices(
            forward_book_value_per_share=pricing_bvps_band,
            multiples=pricing_pb_band,
        ))
        if values:
            method_prices["pb_roe"] = values
            methods.append({
                "code": "pb_roe", "label": "PB / ROE", "weight": DEFAULT_WEIGHTS["pb_roe"],
                "prices": values,
                "formula": "目标价 = 目标年度每股净资产 × 情景 PB；直接使用同年度机构预测，不再用隐藏留存率外推",
                "inputs": {
                    "forward_book_value_per_share": pricing_bvps_band,
                    "forward_roe": forward_roe,
                    "pb": pricing_pb_band,
                    "target_fiscal_year": target_year,
                    "observed_dividend_policy": dividend_retention,
                    "retention_used_in_price": False,
                },
                "provenance": {
                    "book_value_source": forecast.get("provider") if forecast else None,
                    "book_value_scenario_source": "target-year consensus mean stressed -5%/0%/+5%",
                    "multiple_source": "eastmoney_valuation_quantiles" if not pb_fallback else "current_pb_fallback",
                    "dividend_source": dividend_retention.get("source") if dividend_retention else None,
                },
            })

    if "ev_ebitda" in req.methods:
        ev_multiples = {"bear": 8.0, "base": 12.0, "bull": 16.0}
        ev_values, ev_traces = ev_ebitda_analysis(
            ebitda=ttm_ebitda, net_debt=net_debt, shares=shares,
            multiples=ev_multiples, horizon_years=req.horizon_years,
            growth_rates=applied_growth or None,
        )
        values = _round_prices(ev_values)
        if values:
            method_prices["ev_ebitda"] = values
            methods.append({
                "code": "ev_ebitda", "label": "EV / EBITDA", "weight": DEFAULT_WEIGHTS["ev_ebitda"],
                "prices": values,
                "formula": "目标价 = (前瞻 EBITDA × EV/EBITDA − 净债务) ÷ 总股本",
                "calculation_trace": ev_traces,
                "inputs": {
                    "ttm_ebitda": ttm_ebitda, "net_debt": net_debt,
                    "shares": shares, "ev_ebitda": ev_multiples,
                    "raw_eps_implied_growth": raw_growth,
                    "applied_ebitda_growth_proxy": applied_growth or {"bear": 0.02, "base": 0.08, "bull": 0.14},
                    "target_fiscal_year": target_year,
                },
                "provenance": {
                    "financial_source": req.financial_source,
                    "growth_source": "target-year EPS growth proxy with explicit caps" if applied_growth else "normalized config assumption",
                    "multiple_source": "phase_1_5_config_assumption",
                },
            })

    if "dcf" in req.methods:
        dcf_values, dcf_traces = dcf_analysis(
            free_cash_flow=ttm_fcf, net_debt=net_debt, shares=shares,
            near_term_growth=applied_growth or None,
            horizon_years=req.horizon_years,
        )
        values = _round_prices(dcf_values)
        if values:
            method_prices["dcf"] = values
            methods.append({
                "code": "dcf", "label": "FCFF DCF", "weight": DEFAULT_WEIGHTS["dcf"],
                "prices": values,
                "formula": "目标价 = (5 年显式期 FCFF 现值 + 终值现值 − 净债务) ÷ 总股本；近端增长向永续增长逐年收敛",
                "calculation_trace": dcf_traces,
                "inputs": {
                    "ttm_fcff": ttm_fcf, "net_debt": net_debt, "shares": shares,
                    "raw_eps_implied_growth": raw_growth,
                    "applied_near_term_fcff_growth_proxy": applied_growth or {"bear": 0.03, "base": 0.08, "bull": 0.13},
                    "growth_caps": {"bear": 0.30, "base": 0.40, "bull": 0.50},
                    "assumptions": {"bear": {"wacc": 0.115, "terminal_growth": 0.02}, "base": {"wacc": 0.10, "terminal_growth": 0.025}, "bull": {"wacc": 0.085, "terminal_growth": 0.03}},
                },
                "provenance": {
                    "financial_source": req.financial_source,
                    "fcf_field": "FREE_CASH_FLOW",
                    "fcf_definition": "企业自由现金流量（FCFF）",
                    "equity_bridge": "enterprise_value_minus_net_debt_once",
                    "growth_source": "target-year EPS growth used as capped cash-conversion proxy" if applied_growth else "normalized config assumption",
                },
            })

    if "forward_pe" in method_prices and not pe_fallback:
        warnings.append({
            "code": "FORWARD_PE_MULTIPLE_PROXY",
            "message": (
                "Forward PE 的盈利已与目标年度对齐，但倍数带仍来自历史 TTM PE 分位数。"
                "在历史 Forward PE、同行 Forward PE 与增长校准完成前，主区间属于可审计代理，不是最终校准结果。"
            ),
        })
    if "forward_pe" in method_prices:
        warnings.append({
            "code": "CONSENSUS_RANGE_NOT_TAIL_STRESS",
            "message": (
                "页面低/中/高三档表示一致预期分布，不包含增长逻辑被证伪、ROE 回归中枢或行业深度下行。"
                "低一致预期价不能直接当作极端底价或买入价。"
            ),
        })
        if consensus_report_age_days is None:
            warnings.append({
                "code": "CONSENSUS_REPORT_FRESHNESS_UNKNOWN",
                "message": "一致预期有抓取快照日，但缺少可验证的最新机构报告日期；不能假设所有机构已更新最新财报。",
            })
        elif consensus_report_age_days > 60:
            warnings.append({
                "code": "CONSENSUS_REPORT_STALE",
                "message": (
                    f"最新可见机构报告距信息截止日已有 {consensus_report_age_days} 天；"
                    "一致预期可能尚未覆盖近期业绩或事件。"
                ),
            })
    if applied_growth and any(method in method_prices for method in ("ev_ebitda", "dcf")):
        warnings.append({
            "code": "CASHFLOW_GROWTH_PROXY",
            "message": (
                "缺少逐年收入、利润率、CAPEX、营运资本及 EBITDA 预测，近端增长暂以目标年度 EPS 增长代理并封顶。"
                "DCF/EV 的逐步计算已展示，但在完整经营预测接入前只适合作交叉验证。"
            ),
        })

    unavailable_reasons = {
        "forward_pe": f"缺少信息截止日前的 {target_year}E EPS 快照或可用 PE 倍数带；不会退化为 TTM EPS",
        "pb_roe": f"缺少信息截止日前的 {target_year}E 每股净资产预测或可用 PB 倍数带；不会使用隐藏留存率外推",
        "ev_ebitda": "该 PIT 时点缺少正的 TTM EBITDA、总股本或净债务数据",
        "dcf": "该 PIT 时点缺少正的 TTM FCFF、总股本或净债务数据",
    }
    unavailable_methods = [
        {"code": method, "reason": unavailable_reasons[method]}
        for method in req.methods if method not in method_prices
    ]
    for item in unavailable_methods:
        warnings.append({
            "code": f"{str(item['code']).upper()}_UNAVAILABLE",
            "message": str(item["reason"]),
        })

    effective_weights, weight_profile, weight_rationale = _valuation_weights(
        raw_growth=raw_growth,
        forward_roe=forward_roe,
    )
    combined = _round_prices(combine_method_prices(
        method_prices, weights=effective_weights,
    ))
    if not combined:
        raise ValuationDataError("insufficient inputs for every selected valuation method")
    aggregation = _aggregation_policy(
        weight_profile=weight_profile,
        method_prices=method_prices,
        blended_reference=combined,
    )
    headline_range = aggregation["headline"]
    for method in methods:
        code = str(method.get("code"))
        role = aggregation["method_roles"].get(code, "blended")
        method["weight"] = effective_weights.get(code, 0.0)
        method["role"] = role
        method["included_in_headline"] = (
            role in ("primary", "blended")
        )
    if aggregation["mode"] == "primary_with_cross_checks":
        warnings.append({
            "code": "HIGH_GROWTH_PRIMARY_WITH_CROSS_CHECKS",
            "message": (
                "高增长画像不再把口径尚不完整的 DCF/EV 与主模型机械平均。主区间来自 Forward PE；"
                "PB、EV/EBITDA、DCF 仅作护栏/交叉验证，全方法加权值单独保留为诊断参考。"
            ),
        })
    pe_pb_coherence = (
        _pe_pb_coherence(
            eps=pricing_eps_band,
            bvps=pricing_bvps_band,
            pe=pricing_pe_band,
            pb=pricing_pb_band,
        )
        if "forward_pe" in method_prices and "pb_roe" in method_prices else {}
    )
    if pe_pb_coherence.get("status") == "severely_divergent":
        warnings.append({
            "code": "PE_PB_COHERENCE_DIVERGENCE",
            "message": (
                "Forward PE 隐含的 PB（PE×Forward ROE）与历史 PB 锚严重背离，"
                "说明两组倍数不属于同一盈利阶段；PB 仅用于提示口径分歧，不作为主模型否决器。"
            ),
        })
    if len(method_prices) < 2:
        warnings.append({
            "code": "LOW_METHOD_COVERAGE",
            "message": "少于两种估值方法可计算，综合区间的稳健性较低。",
        })
    if ttm_fcf is not None and ttm_fcf <= 0:
        warnings.append({
            "code": "NON_POSITIVE_FCF",
            "message": "TTM 自由现金流非正，DCF 被禁用。",
        })

    latest_financial = max(
        [row for row in (income_rows + balance_rows + cashflow_rows) if row.get("reporting_period")],
        key=lambda row: str(row.get("reporting_period")),
    )
    institution_count = number(eps_extra.get("institution_count")) or 0.0
    source_score = min(institution_count / 10.0, 1.0) * 12
    if eps_extra.get("range_source") == "institution_detail":
        source_score += 5
    if bvps_forecast and roe_forecast:
        source_score += 3
    alignment_score = 0.0
    alignment_score += 10 if "forward_pe" in method_prices and has_consensus else 0
    alignment_score += 10 if "pb_roe" in method_prices and bvps_forecast and roe_forecast else 0
    alignment_score += 2 if "ev_ebitda" in method_prices and applied_growth else 0
    alignment_score += 2 if "dcf" in method_prices and applied_growth else 0
    confidence = confidence_score(
        has_price=True,
        financial_statement_count=len(income_rows) + len(balance_rows) + len(cashflow_rows),
        historical_multiple_count=max(len(history["pe"]), len(history["pb"])),
        valid_method_count=len(method_prices),
        selected_method_count=len(req.methods),
        forecast_alignment_score=alignment_score,
        forecast_source_score=source_score,
        pit_integrity_score=15,
        method_base_values=[prices.get("base") for prices in method_prices.values()],
    )
    market_price = price["close"]
    pe_sensitivity = (
        _forward_pe_sensitivity(
            eps=pricing_eps_band,
            multiples=pricing_pe_band,
            market_price=market_price,
        )
        if "forward_pe" in method_prices else {}
    )
    confidence_components = {
        str(item.get("code")): item for item in confidence.get("components", [])
    }
    confidence_gates: List[Dict[str, Any]] = []
    agreement_component_score = number(
        (confidence_components.get("model_agreement") or {}).get("score")
    )
    if agreement_component_score is None or agreement_component_score < 4:
        confidence_gates.append({
            "code": "MODEL_DISAGREEMENT_CAP",
            "score_cap": 69,
            "reason": "交叉方法基准值严重分歧，整体评分不能进入高可信区间。",
        })
    historical_component_score = number(
        (confidence_components.get("historical_stability") or {}).get("score")
    )
    if historical_component_score is None or historical_component_score < 5:
        confidence_gates.append({
            "code": "NO_HISTORICAL_VALIDATION",
            "score_cap": 84,
            "reason": "真实历史一致预期样本尚未积累，不能用事后预测补回测。",
        })
    primary_is_proxy = aggregation.get("primary_method") == "forward_pe"
    confidence.update({
        "usage_status": "provisional" if primary_is_proxy else "limited",
        "usage_label": "试验性情景参考" if primary_is_proxy else "有限参考",
        "score_semantics": "数据覆盖、PIT 和结构完整度评分；不是上涨概率、目标价命中率或买入评级。",
        "decision_use": "scenario_reference_only",
        "gates": confidence_gates,
        "dimensions": [
            {
                "code": "data_and_pit",
                "label": "数据与时点",
                "status": "high" if alignment_score >= 20 and source_score >= 12 else "medium",
                "reason": "评价财报、预测和价格是否在信息截止日前可得。",
            },
            {
                "code": "primary_model",
                "label": "主模型校准",
                "status": "provisional" if primary_is_proxy else "limited",
                "reason": "历史 TTM PE 仍是 Forward PE 代理，尚缺同行/历史 Forward 倍数。" if primary_is_proxy else "主模型仍需更多历史样本校准。",
            },
            {
                "code": "cross_check_agreement",
                "label": "交叉验证一致性",
                "status": "low" if pe_pb_coherence.get("status") == "severely_divergent" else "medium",
                "reason": pe_pb_coherence.get("interpretation") or "可用交叉方法有限。",
            },
            {
                "code": "historical_validation",
                "label": "历史前瞻验证",
                "status": "unavailable",
                "reason": "从真实抓取日起积累快照；当前不生成后见之明样本。",
            },
        ],
    })
    price_reference = _price_reference_guide(
        headline_range=headline_range,
        market_price=market_price,
        pe_sensitivity=pe_sensitivity,
    )
    return {
        "security": {
            "security_id": req.security_id,
            "symbol": security.get("symbol") or price.get("symbol"),
            "name": security.get("name") or latest_financial.get("security_name"),
            "exchange": security.get("exchange"),
        },
        "valuation_date": valuation_date,
        "price_as_of": price["date"],
        "market_price": round(market_price, 2),
        "horizon_years": req.horizon_years,
        "range": {
            **headline_range,
            "upside_base": round(headline_range.get("base", market_price) / market_price - 1, 4),
            "market_position": "below_range" if market_price < min(headline_range.values()) else "above_range" if market_price > max(headline_range.values()) else "inside_range",
        },
        "matrix": {
            "scenarios": list(SCENARIOS),
            "scenario_definitions": SCENARIO_DEFINITIONS,
            "methods": methods,
            "unavailable_methods": unavailable_methods,
            "combined": combined,
            "weights": effective_weights,
            "weight_profile": weight_profile,
            "weight_rationale": weight_rationale,
            "aggregation": aggregation,
        },
        "forward_pe_sensitivity": pe_sensitivity or None,
        "price_reference": price_reference or None,
        "diagnostics": {
            "pe_pb_coherence": pe_pb_coherence or None,
        },
        "fundamentals": {
            "ttm_net_profit": ttm_profit,
            "ttm_revenue": ttm_revenue,
            "ttm_ebitda": ttm_ebitda,
            "ttm_free_cash_flow": ttm_fcf,
            "shares": shares,
            "book_value_per_share": bvps,
            "ttm_eps": actual_eps,
            "ttm_roe": roe,
            "observed_dividend_policy": dividend_retention,
            "cash": cash,
            "interest_bearing_debt": debt,
            "net_debt": net_debt,
        },
        "confidence": confidence,
        "warnings": warnings,
        "point_in_time": {
            "information_as_of": valuation_date,
            "price_as_of": price["date"],
            "price_source": price.get("price_source", "phoenixA_bars"),
            "financial_available_at": latest_financial.get("actual_ann_date") or latest_financial.get("ann_date"),
            "financial_reporting_period": latest_financial.get("reporting_period"),
            "consensus_as_of": forecast.get("trade_date") if forecast else None,
            "consensus_source": forecast.get("provider") if forecast else None,
            "consensus_latest_report_date": latest_consensus_report_date,
            "consensus_latest_report_age_days": consensus_report_age_days,
            "target_fiscal_year": target_year,
            "history_start": history.get("start_date"),
            "rule": "price_date <= information_as_of; announcement_date <= information_as_of; consensus_snapshot_date <= information_as_of; all forward inputs match target_fiscal_year",
        },
    }


def valuation_eligibility(
    *,
    security_id: int,
    valuation_date: date | None = None,
) -> Dict[str, Any]:
    try:
        req = ValuationAnalyzeRequest(
            security_id=security_id,
            valuation_date=valuation_date,
            methods=["forward_pe", "pb_roe"],
        )
        result = analyze_valuation(req)
        return {
            "eligible": True,
            "security": result["security"],
            "price_as_of": result["price_as_of"],
            "financial_reporting_period": result["point_in_time"]["financial_reporting_period"],
            "warnings": result["warnings"],
        }
    except (ValuationDataError, ValueError) as exc:
        return {"eligible": False, "security_id": security_id, "reason": str(exc)}


def replay_valuation_history(req: ValuationHistoryRequest) -> Dict[str, Any]:
    frequency = "ME" if req.interval == "month_end" else "QE"
    dates = list(pd.date_range(req.start_date, req.end_date, freq=frequency))
    if not dates or dates[-1].date() != req.end_date:
        dates.append(pd.Timestamp(req.end_date))
    if len(dates) > 60:
        raise ValuationDataError("history replay is limited to 60 evaluation points")
    points: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    security: Dict[str, Any] | None = None
    for evaluation_date in dates:
        analyze_req = ValuationAnalyzeRequest(
            security_id=req.security_id,
            valuation_date=evaluation_date.date(),
            history_years=req.history_years,
            financial_source=req.financial_source,
            statement_code=req.statement_code,
        )
        try:
            result = analyze_valuation(analyze_req)
        except (ValuationDataError, ValueError) as exc:
            skipped.append({"valuation_date": evaluation_date.strftime("%Y-%m-%d"), "reason": str(exc)})
            continue
        security = result["security"]
        points.append({
            "valuation_date": result["valuation_date"],
            "price_as_of": result["price_as_of"],
            "market_price": result["market_price"],
            "bear": result["range"].get("bear"),
            "base": result["range"].get("base"),
            "bull": result["range"].get("bull"),
            "upside_base": result["range"].get("upside_base"),
            "confidence": result["confidence"],
            "warning_codes": [warning["code"] for warning in result["warnings"]],
        })
    return {
        "security": security or {"security_id": req.security_id},
        "start_date": req.start_date.isoformat(),
        "end_date": req.end_date.isoformat(),
        "interval": req.interval,
        "points": points,
        "skipped": skipped,
        "point_in_time": True,
    }

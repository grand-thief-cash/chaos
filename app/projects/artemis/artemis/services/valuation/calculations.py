from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping


SCENARIOS = ("bear", "base", "bull")
DEFAULT_WEIGHTS = {
    "forward_pe": 0.40,
    "pb_roe": 0.30,
    "ev_ebitda": 0.20,
    "dcf": 0.10,
}


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def percentile(values: Iterable[Any], quantile: float) -> float | None:
    cleaned = sorted(
        value for item in values
        if (value := number(item)) is not None and value > 0
    )
    if not cleaned:
        return None
    position = min(max(quantile, 0.0), 1.0) * (len(cleaned) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return cleaned[lower]
    fraction = position - lower
    return cleaned[lower] * (1 - fraction) + cleaned[upper] * fraction


def multiple_band(values: Iterable[Any], *, floor: float, cap: float) -> Dict[str, float] | None:
    cleaned = [
        value for item in values
        if (value := number(item)) is not None and floor <= value <= cap
    ]
    if not cleaned:
        return None
    q25 = percentile(cleaned, 0.25)
    q50 = percentile(cleaned, 0.50)
    q75 = percentile(cleaned, 0.75)
    if q25 is None or q50 is None or q75 is None:
        return None
    return {"bear": q25, "base": q50, "bull": q75}


def forward_pe_prices(
    eps: Mapping[str, Any],
    multiples: Mapping[str, Any],
) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for scenario in SCENARIOS:
        earnings = number(eps.get(scenario))
        multiple = number(multiples.get(scenario))
        if earnings is not None and earnings > 0 and multiple is not None and multiple > 0:
            result[scenario] = earnings * multiple
    return result


def pb_roe_prices(
    *,
    forward_book_value_per_share: Mapping[str, Any],
    multiples: Mapping[str, Any],
) -> Dict[str, float]:
    """Price an exact target-year BVPS forecast; never synthesize retention."""
    result: Dict[str, float] = {}
    for scenario in SCENARIOS:
        bvps = number(forward_book_value_per_share.get(scenario))
        multiple = number(multiples.get(scenario))
        if bvps is not None and bvps > 0 and multiple is not None and multiple > 0:
            result[scenario] = bvps * multiple
    return result


def forward_growth_rates(
    *,
    current_value: Any,
    target_values: Mapping[str, Any],
    horizon_years: int,
) -> tuple[Dict[str, float], Dict[str, float]]:
    """Return raw and capped annual growth implied by target-year forecasts.

    EPS growth is only a proxy for EBITDA/FCFF growth. Caps prevent a single
    boom-year forecast from being compounded for the entire explicit period;
    callers must expose both raw and applied rates to users.
    """
    current = number(current_value)
    if current is None or current <= 0 or horizon_years <= 0:
        return {}, {}
    caps = {"bear": 0.30, "base": 0.40, "bull": 0.50}
    raw: Dict[str, float] = {}
    applied: Dict[str, float] = {}
    for scenario in SCENARIOS:
        target = number(target_values.get(scenario))
        if target is None or target <= 0:
            continue
        rate = (target / current) ** (1 / horizon_years) - 1
        raw[scenario] = rate
        applied[scenario] = min(max(rate, -0.15), caps[scenario])
    return raw, applied


def ev_ebitda_analysis(
    *,
    ebitda: Any,
    net_debt: Any,
    shares: Any,
    multiples: Mapping[str, Any],
    horizon_years: int,
    growth_rates: Mapping[str, Any] | None = None,
) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    base_ebitda = number(ebitda)
    debt = number(net_debt)
    share_count = number(shares)
    if base_ebitda is None or base_ebitda <= 0 or debt is None or not share_count or share_count <= 0:
        return {}, {}
    growth = growth_rates or {"bear": 0.02, "base": 0.08, "bull": 0.14}
    result: Dict[str, float] = {}
    traces: Dict[str, Dict[str, Any]] = {}
    for scenario in SCENARIOS:
        multiple = number(multiples.get(scenario))
        if multiple is None or multiple <= 0:
            continue
        rate = number(growth.get(scenario))
        if rate is None or rate <= -1:
            continue
        forward_ebitda = base_ebitda * ((1 + rate) ** horizon_years)
        enterprise_value = forward_ebitda * multiple
        equity_value = enterprise_value - debt
        if equity_value > 0:
            price = equity_value / share_count
            result[scenario] = price
            traces[scenario] = {
                "starting_ttm_ebitda": base_ebitda,
                "growth_rate": rate,
                "horizon_years": horizon_years,
                "forward_ebitda": forward_ebitda,
                "multiple": multiple,
                "enterprise_value": enterprise_value,
                "net_debt": debt,
                "equity_value": equity_value,
                "shares": share_count,
                "price": price,
                "currency_unit": "CNY",
                "share_unit": "share",
            }
    return result, traces


def ev_ebitda_prices(
    *,
    ebitda: Any,
    net_debt: Any,
    shares: Any,
    multiples: Mapping[str, Any],
    horizon_years: int,
    growth_rates: Mapping[str, Any] | None = None,
) -> Dict[str, float]:
    prices, _ = ev_ebitda_analysis(
        ebitda=ebitda,
        net_debt=net_debt,
        shares=shares,
        multiples=multiples,
        horizon_years=horizon_years,
        growth_rates=growth_rates,
    )
    return prices


def dcf_analysis(
    *,
    free_cash_flow: Any,
    net_debt: Any,
    shares: Any,
    explicit_years: int = 5,
    near_term_growth: Mapping[str, Any] | None = None,
    horizon_years: int = 1,
) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    fcf = number(free_cash_flow)
    debt = number(net_debt)
    share_count = number(shares)
    if fcf is None or fcf <= 0 or debt is None or not share_count or share_count <= 0:
        return {}, {}
    assumptions = {
        "bear": {"growth": 0.03, "wacc": 0.115, "terminal_growth": 0.020},
        "base": {"growth": 0.08, "wacc": 0.100, "terminal_growth": 0.025},
        "bull": {"growth": 0.13, "wacc": 0.085, "terminal_growth": 0.030},
    }
    result: Dict[str, float] = {}
    traces: Dict[str, Dict[str, Any]] = {}
    for scenario, assumption in assumptions.items():
        growth = number((near_term_growth or {}).get(scenario))
        if growth is None:
            growth = assumption["growth"]
        wacc = assumption["wacc"]
        terminal_growth = assumption["terminal_growth"]
        projected = fcf
        present_value = 0.0
        years: list[Dict[str, Any]] = []
        for year in range(1, explicit_years + 1):
            if near_term_growth and year > horizon_years:
                fade_years = max(explicit_years - horizon_years, 1)
                progress = min((year - horizon_years) / fade_years, 1.0)
                year_growth = growth + (terminal_growth - growth) * progress
            else:
                year_growth = growth
            projected *= 1 + year_growth
            discount_factor = (1 + wacc) ** year
            present_value_year = projected / discount_factor
            present_value += present_value_year
            years.append({
                "year": year,
                "growth_rate": year_growth,
                "projected_fcff": projected,
                "discount_factor": discount_factor,
                "present_value_fcff": present_value_year,
            })
        terminal_value = projected * (1 + terminal_growth) / (wacc - terminal_growth)
        terminal_present_value = terminal_value / ((1 + wacc) ** explicit_years)
        enterprise_value = present_value + terminal_present_value
        equity_value = enterprise_value - debt
        if equity_value > 0:
            price = equity_value / share_count
            result[scenario] = price
            traces[scenario] = {
                "starting_ttm_fcff": fcf,
                "near_term_growth": growth,
                "horizon_years": horizon_years,
                "explicit_years": explicit_years,
                "fade_rule": (
                    "linear_to_terminal_after_target_horizon"
                    if near_term_growth else "constant_normalized_growth"
                ),
                "wacc": wacc,
                "terminal_growth": terminal_growth,
                "years": years,
                "explicit_present_value": present_value,
                "terminal_value_at_year_end": terminal_value,
                "terminal_present_value": terminal_present_value,
                "enterprise_value": enterprise_value,
                "net_debt": debt,
                "equity_value": equity_value,
                "shares": share_count,
                "price": price,
                "currency_unit": "CNY",
                "share_unit": "share",
            }
    return result, traces


def dcf_prices(
    *,
    free_cash_flow: Any,
    net_debt: Any,
    shares: Any,
    explicit_years: int = 5,
    near_term_growth: Mapping[str, Any] | None = None,
    horizon_years: int = 1,
) -> Dict[str, float]:
    prices, _ = dcf_analysis(
        free_cash_flow=free_cash_flow,
        net_debt=net_debt,
        shares=shares,
        explicit_years=explicit_years,
        near_term_growth=near_term_growth,
        horizon_years=horizon_years,
    )
    return prices


def combine_method_prices(
    method_prices: Mapping[str, Mapping[str, Any]],
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> Dict[str, float]:
    combined: Dict[str, float] = {}
    for scenario in SCENARIOS:
        numerator = 0.0
        denominator = 0.0
        for method, prices in method_prices.items():
            value = number(prices.get(scenario))
            weight = max(float(weights.get(method, 0.0)), 0.0)
            if value is None or value <= 0 or weight <= 0:
                continue
            numerator += value * weight
            denominator += weight
        if denominator:
            combined[scenario] = numerator / denominator
    # Present a coherent low/base/high range even when method crossings make
    # raw scenario averages non-monotonic.
    if len(combined) == 3:
        ordered = sorted(combined.values())
        return {"bear": ordered[0], "base": ordered[1], "bull": ordered[2]}
    return combined


def confidence_score(
    *,
    has_price: bool,
    financial_statement_count: int,
    historical_multiple_count: int,
    valid_method_count: int,
    selected_method_count: int,
    forecast_alignment_score: float,
    forecast_source_score: float,
    pit_integrity_score: float,
    method_base_values: Iterable[Any],
    historical_backtest_score: float = 0.0,
) -> Dict[str, Any]:
    price_score = 4.0 if has_price else 0.0
    financial_score = min(max(financial_statement_count, 0) / 12, 1.0) * 8
    history_score = min(max(historical_multiple_count, 0) / 120, 1.0) * 4
    selected = max(selected_method_count, 1)
    coverage_score = min(max(valid_method_count, 0) / selected, 1.0) * 4
    data_score = price_score + financial_score + history_score + coverage_score

    bases = sorted(
        value for item in method_base_values
        if (value := number(item)) is not None and value > 0
    )
    if len(bases) < 2:
        agreement_score = 2.0 if bases else 0.0
        agreement_reason = "少于两种方法，无法充分检验模型一致性"
    else:
        spread = bases[-1] / bases[0]
        if spread <= 1.30:
            agreement_score = 15.0
        elif spread <= 1.60:
            agreement_score = 12.0
        elif spread <= 2.00:
            agreement_score = 8.0
        elif spread <= 3.00:
            agreement_score = 4.0
        else:
            agreement_score = 0.0
        agreement_reason = f"方法基准值最大/最小为 {spread:.2f} 倍"

    components = [
        {"code": "data_quality", "label": "数据完整性", "score": round(data_score, 1), "max_score": 20, "reason": "价格、财报、历史倍数与方法覆盖"},
        {"code": "forecast_alignment", "label": "预测时间对齐", "score": round(min(max(forecast_alignment_score, 0), 25) * 0.8, 1), "max_score": 20, "reason": "目标年度预测与估值年度是否一致"},
        {"code": "forecast_source", "label": "预测来源质量", "score": round(min(max(forecast_source_score, 0), 20) * 0.75, 1), "max_score": 15, "reason": "机构数量、逐家预测与详细指标覆盖"},
        {"code": "pit_integrity", "label": "PIT 完整性", "score": round(min(max(pit_integrity_score, 0), 15), 1), "max_score": 15, "reason": "数据发布时间不晚于信息截止日"},
        {"code": "model_agreement", "label": "模型一致性", "score": round(agreement_score, 1), "max_score": 15, "reason": agreement_reason},
        {"code": "historical_stability", "label": "历史稳定性", "score": round(min(max(historical_backtest_score, 0), 15), 1), "max_score": 15, "reason": "需要真实历史预测快照才能回测；当前不以事后预测补历史"},
    ]
    score = int(round(min(sum(item["score"] for item in components), 100)))
    # Critical dimensions are gates, not merely additive bonuses. A model with
    # badly diverging methods or no time-aligned forecast must not compensate
    # its way to "high" confidence through abundant historical rows.
    if agreement_score < 4:
        score = min(score, 69)
    if forecast_alignment_score < 12:
        score = min(score, 49)
    if forecast_source_score < 8:
        score = min(score, 59)
    if historical_backtest_score < 5:
        score = min(score, 84)
    label = "high" if score >= 75 else "medium" if score >= 50 else "low"
    return {"score": score, "label": label, "components": components}

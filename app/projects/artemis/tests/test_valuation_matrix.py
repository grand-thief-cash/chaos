from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd

from artemis.api.http_gateway.workbench_routes import router
from artemis.engines.task_engine.download.zh.stock_zh_a_earnings_consensus import (
    StockZHAEarningsConsensus,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_equity_structure import (
    StockZHAEquityStructure,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_valuation_daily import (
    StockZHAValuationDaily,
)
from artemis.services.valuation.calculations import (
    combine_method_prices,
    confidence_score,
    dcf_analysis,
    dcf_prices,
    ev_ebitda_analysis,
    forward_growth_rates,
    forward_pe_prices,
    multiple_band,
    pb_roe_prices,
)
from artemis.services.valuation.service import (
    _aggregation_policy,
    _dividend_retention_as_of,
    _forecast_bundle_as_of,
    _forward_pe_sensitivity,
    _pe_pb_coherence,
    _price_as_of,
    _price_reference_guide,
    _round_scenario_inputs,
    _valuation_weights,
)


class FakeLogger:
    def info(self, _message):
        pass

    def warning(self, _message):
        pass


class FakeCtx:
    def __init__(self, params=None):
        self.params = params or {}
        self.run_id = "valuation-test"
        self.logger = FakeLogger()


def test_multiple_band_and_weighted_matrix_are_deterministic():
    band = multiple_band([10, 20, 30, 40, -1, 999], floor=5, cap=100)
    assert band == {"bear": 17.5, "base": 25.0, "bull": 32.5}
    pe = forward_pe_prices(
        {"bear": 1.0, "base": 2.0, "bull": 3.0}, band,
    )
    combined = combine_method_prices({
        "forward_pe": pe,
        "pb_roe": {"bear": 20, "base": 50, "bull": 100},
    })
    assert combined["bear"] < combined["base"] < combined["bull"]


def test_dcf_uses_net_debt_equity_bridge_and_scenario_order():
    low_debt = dcf_prices(free_cash_flow=100, net_debt=10, shares=10)
    high_debt = dcf_prices(free_cash_flow=100, net_debt=100, shares=10)
    assert low_debt["bear"] < low_debt["base"] < low_debt["bull"]
    assert high_debt["base"] < low_debt["base"]


def test_ev_ebitda_trace_keeps_yuan_units_and_explains_price():
    prices, traces = ev_ebitda_analysis(
        ebitda=7_407_245_388.45,
        net_debt=4_344_779_684.82,
        shares=2_429_119_230,
        multiples={"bear": 8, "base": 12, "bull": 16},
        horizon_years=1,
        growth_rates={"bear": 0.3, "base": 0.4, "bull": 0.5},
    )
    base = traces["base"]
    assert round(base["forward_ebitda"] / 1e8, 2) == 103.70
    assert round(base["enterprise_value"] / 1e8, 2) == 1244.42
    assert round(base["price"], 2) == round(prices["base"], 2) == 49.44


def test_dcf_trace_exposes_fade_path_and_equity_bridge():
    prices, traces = dcf_analysis(
        free_cash_flow=3_152_695_731.3884006,
        net_debt=4_344_779_684.82,
        shares=2_429_119_230,
        near_term_growth={"bear": 0.3, "base": 0.4, "bull": 0.5},
        horizon_years=1,
    )
    base = traces["base"]
    growth_path = [round(year["growth_rate"], 4) for year in base["years"]]
    assert growth_path == [0.4, 0.3063, 0.2125, 0.1188, 0.025]
    assert round(base["enterprise_value"] - base["net_debt"], 2) == round(base["equity_value"], 2)
    assert round(base["price"], 2) == round(prices["base"], 2) == 36.24


def test_high_growth_uses_primary_model_and_keeps_blend_as_diagnostic():
    aggregation = _aggregation_policy(
        weight_profile="high_growth",
        method_prices={
            "forward_pe": {"bear": 65.72, "base": 110.07, "bull": 179.76},
            "dcf": {"bear": 23.06, "base": 36.24, "bull": 60.57},
        },
        blended_reference={"bear": 60.0, "base": 100.0, "bull": 160.0},
    )
    assert aggregation["mode"] == "primary_with_cross_checks"
    assert aggregation["headline"]["base"] == 110.07
    assert aggregation["blended_reference"]["base"] == 100.0
    assert aggregation["method_roles"] == {"forward_pe": "primary", "dcf": "cross_check"}


def test_forward_pe_sensitivity_decouples_eps_and_multiple_scenarios():
    matrix = _forward_pe_sensitivity(
        eps={"bear": 3.03, "base": 3.48, "bull": 4.51},
        multiples={"bear": 21.69, "base": 31.60, "bull": 39.86},
        market_price=143.21,
    )
    assert matrix["grid"]["bull"]["base"] == 142.52
    assert matrix["market_implied"]["forward_pe_at_base_eps"] == 41.15
    assert matrix["market_implied"]["nearest_grid_cell"]["eps_scenario"] == "bull"
    assert matrix["market_implied"]["nearest_grid_cell"]["multiple_scenario"] == "base"


def test_forward_pe_displayed_operands_reproduce_every_grid_price():
    eps = _round_scenario_inputs({"bear": 3.030049, "base": 3.48376, "bull": 4.50997})
    multiples = _round_scenario_inputs({"bear": 21.68881, "base": 31.59837, "bull": 39.85991})
    matrix = _forward_pe_sensitivity(eps=eps, multiples=multiples, market_price=143.21)
    for eps_scenario, eps_value in eps.items():
        for pe_scenario, multiple in multiples.items():
            assert matrix["grid"][eps_scenario][pe_scenario] == round(eps_value * multiple, 2)


def test_pe_pb_coherence_exposes_incompatible_valuation_stories():
    diagnostic = _pe_pb_coherence(
        eps={"bear": 3.03, "base": 3.48, "bull": 4.51},
        bvps={"bear": 9.94, "base": 10.46, "bull": 10.98},
        pe={"bear": 21.69, "base": 31.60, "bull": 39.86},
        pb={"bear": 3.14, "base": 3.37, "bull": 3.78},
    )
    assert diagnostic["status"] == "severely_divergent"
    assert diagnostic["rows"]["base"]["coherent_pb"] > 10
    assert diagnostic["base_gap_ratio"] > 3


def test_price_reference_does_not_mislabel_low_consensus_as_tail_stress():
    sensitivity = _forward_pe_sensitivity(
        eps={"bear": 3.03, "base": 3.48, "bull": 4.51},
        multiples={"bear": 21.69, "base": 31.60, "bull": 39.86},
        market_price=143.21,
    )
    guide = _price_reference_guide(
        headline_range={"bear": 65.72, "base": 110.07, "bull": 179.76},
        market_price=143.21,
        pe_sensitivity=sensitivity,
    )
    assert guide["state"] == "between_base_and_high"
    assert guide["tail_stress_available"] is False
    assert len(guide["usage_rules"]) == 4


def test_equity_structure_normalizes_and_deduplicates():
    task = StockZHAEquityStructure()
    task._security_map = {"600183.SH": {"security_id": 4889}}
    frame = pd.DataFrame([
        {"MARKET_CODE": "600183.SH", "ANN_DATE": "20240102", "CHANGE_DATE": "20240101", "CURRENT_SIGN": 1, "IS_VALID": 1, "TOTAL_SHARES": 100},
        {"MARKET_CODE": "600183.SH", "ANN_DATE": "20240102", "CHANGE_DATE": "20240101", "CURRENT_SIGN": 1, "IS_VALID": 1, "TOTAL_SHARES": 110},
    ])
    rows = task.post_process(FakeCtx(), frame)
    assert len(rows) == 1
    assert rows[0]["security_id"] == 4889
    assert rows[0]["ann_date"] == "2024-01-02"
    assert rows[0]["data_json"]["TOTAL_SHARES"] == 110


def test_daily_valuation_expands_vendor_row_into_typed_observations():
    task = StockZHAValuationDaily()
    ctx = FakeCtx({
        "pending_securities": [{"security_id": 4889, "symbol": "600183", "effective_start_date": "2020-01-01"}],
        "effective_end_date": "2026-08-16",
    })
    frame = pd.DataFrame([{
        "数据日期": "2026-08-14", "当日收盘价": 143.21,
        "PE(TTM)": 88.55, "市净率": 18.80,
    }])
    rows = task.post_process(ctx, {4889: frame})
    values = {row["observation_type"]: row["value"] for row in rows}
    assert values == {
        "valuation_close": 143.21,
        "valuation_pe_ttm": 88.55,
        "valuation_pb": 18.80,
    }


def test_consensus_snapshot_preserves_range_and_institution_count():
    task = StockZHAEarningsConsensus()
    ctx = FakeCtx({
        "pending_securities": [{"security_id": 4889, "symbol": "600183"}],
        "as_of_date": "2026-08-16",
    })
    frame = pd.DataFrame([{
        "年度": "2027", "预测机构数": 13, "最小值": 1.98,
        "均值": 3.48, "最大值": 5.02, "行业平均数": 4.01,
    }])
    rows = task.post_process(ctx, {"ths": {4889: frame}, "em": None})
    assert rows[0]["observation_type"] == "eps_consensus_2027"
    assert rows[0]["value"] == 3.48
    assert rows[0]["extra_json"]["institution_count"] == 13.0


def test_consensus_prefers_active_institutions_and_persists_forward_fundamentals():
    task = StockZHAEarningsConsensus()
    ctx = FakeCtx({
        "pending_securities": [{"security_id": 4889, "symbol": "600183"}],
        "as_of_date": "2026-08-16",
    })
    summary = pd.DataFrame([{
        "年度": "2027", "预测机构数": 13, "最小值": 1.98,
        "均值": 3.48, "最大值": 5.02,
    }])
    institutions = pd.DataFrame({
        "预测年报每股收益2027预测": [3.03, 3.17, 3.36, 3.51, 3.57, 4.51],
        "报告日期": ["2026-05-01"] * 6,
    })
    details = pd.DataFrame([
        {"预测指标": "每股净资产(元)", "预测2027-平均": "10.46"},
        {"预测指标": "净资产收益率", "预测2027-平均": "35.33%"},
    ])
    rows = task.post_process(ctx, {
        "ths": {4889: summary},
        "ths_institutions": {4889: institutions},
        "ths_details": {4889: details},
        "em": None,
    })
    by_type = {row["observation_type"]: row for row in rows}
    eps = by_type["eps_consensus_2027"]
    assert round(eps["value"], 4) == 3.525
    assert eps["extra_json"]["low"] == 3.03
    assert eps["extra_json"]["high"] == 4.51
    assert eps["extra_json"]["range_source"] == "institution_detail"
    assert eps["extra_json"]["latest_report_date"] == "2026-05-01"
    assert by_type["bvps_consensus_2027"]["value"] == 10.46
    assert by_type["roe_consensus_2027"]["value"] == 0.3533


def test_forward_models_use_target_year_inputs_and_explicit_growth_caps():
    pb = pb_roe_prices(
        forward_book_value_per_share={"bear": 9.5, "base": 10, "bull": 10.5},
        multiples={"bear": 2, "base": 3, "bull": 4},
    )
    assert pb == {"bear": 19.0, "base": 30.0, "bull": 42.0}
    raw, applied = forward_growth_rates(
        current_value=2,
        target_values={"bear": 2.4, "base": 3.0, "bull": 4.0},
        horizon_years=1,
    )
    assert raw["bull"] == 1.0
    assert {key: round(value, 4) for key, value in applied.items()} == {
        "bear": 0.2, "base": 0.4, "bull": 0.5,
    }


def test_forecast_bundle_requires_exact_target_year_and_respects_information_cutoff():
    class FakeClient:
        def query_market_observations(self, *, source, **_kwargs):
            if source != "ths_consensus":
                return []
            return [
                {"trade_date": "2026-08-16", "observation_type": "eps_consensus_2027", "value": 3.48},
                {"trade_date": "2026-08-16", "observation_type": "bvps_consensus_2027", "value": 10.46},
                {"trade_date": "2026-08-16", "observation_type": "eps_consensus_2028", "value": 4.88},
            ]

    bundle = _forecast_bundle_as_of(FakeClient(), 4889, "2026-08-16", 2027)
    assert bundle["fiscal_year"] == 2027
    assert bundle["observations"]["eps"]["value"] == 3.48
    assert bundle["observations"]["bvps"]["value"] == 10.46


def test_dividend_retention_is_observed_not_hidden_assumption():
    class FakeClient:
        def query_corporate_actions(self, **_kwargs):
            return {"rows": [
                {"top_level": {"report_period": "2025-06-30", "progress_code": "3"}, "data_json": {"DVD_PER_SHARE_PRE_TAX_CASH": 0.4}},
                {"top_level": {"report_period": "2025-12-31", "progress_code": "3"}, "data_json": {"DVD_PER_SHARE_PRE_TAX_CASH": 0.8}},
            ]}

    result = _dividend_retention_as_of(
        FakeClient(), security_id=4889, valuation_date="2026-08-16",
        income_rows=[{"report_type": "4", "reporting_period": "2025-12-31", "NET_PRO_EXCL_MIN_INT_INC": 137.25}],
        shares=100,
    )
    assert round(result["payout_ratio"], 4) == 0.8743
    assert round(result["retention_ratio"], 4) == 0.1257


def test_confidence_exposes_components_and_penalizes_missing_forecasts():
    result = confidence_score(
        has_price=True, financial_statement_count=12,
        historical_multiple_count=120, valid_method_count=2,
        selected_method_count=4, forecast_alignment_score=0,
        forecast_source_score=0, pit_integrity_score=15,
        method_base_values=[30, 90],
    )
    assert result["score"] < 50
    assert {item["code"] for item in result["components"]} == {
        "data_quality", "forecast_alignment", "forecast_source",
        "pit_integrity", "model_agreement", "historical_stability",
    }


def test_high_growth_weight_profile_reduces_pb_dominance():
    weights, profile, reason = _valuation_weights(
        raw_growth={"base": 0.45}, forward_roe=0.30,
    )
    assert profile == "high_growth"
    assert weights["forward_pe"] == 0.70
    assert weights["pb_roe"] == 0.05
    assert "盈利模型主导" in reason


def test_price_as_of_falls_back_to_persisted_valuation_close():
    class FakeClient:
        def get_bars(self, **_kwargs):
            return []

        def query_market_observations(self, **_kwargs):
            return [
                {"trade_date": "2024-03-28", "value": 20.5},
                {"trade_date": "2024-03-29", "value": 21.25},
            ]

    assert _price_as_of(FakeClient(), 4889, "2024-03-31") == {
        "date": "2024-03-29",
        "close": 21.25,
        "symbol": "",
        "price_source": "eastmoney_valuation",
    }


def test_valuation_http_config_and_analyze(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    config = client.get("/workbench/valuation/config")
    assert config.status_code == 200
    assert config.json()["consensus_semantics"] == "observed_on_fetch_date_no_synthetic_history"
    assert config.json()["scenario_definitions"]["bear"]["tail_stress"] is False
    assert config.json()["price_reference_policy"]["framework"] == "scenario_reference_not_target_price"

    monkeypatch.setattr(
        "artemis.api.http_gateway.valuation_routes.analyze_valuation",
        lambda req: {"security_id": req.security_id, "range": {"base": 42}},
    )
    response = client.post(
        "/workbench/valuation/analyze",
        json={"security_id": 4889, "valuation_date": "2026-08-16"},
    )
    assert response.status_code == 200
    assert response.json()["range"]["base"] == 42

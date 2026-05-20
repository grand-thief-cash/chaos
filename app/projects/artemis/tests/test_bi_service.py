from __future__ import annotations

from artemis.models.bi import BIPeerComparisonRequest
from artemis.services.bi_service import BIService


class FakePhoenixClient:
    def get_securities(self, **kwargs):
        payload = {
            "000001": {
                "symbol": "000001",
                "name": "测试股份",
                "market": "zh_a",
                "exchange": "SZ",
                "asset_type": "stock",
                "status": "active",
            },
            "600519": {
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "zh_a",
                "exchange": "SH",
                "asset_type": "stock",
                "status": "active",
            },
            "000858": {
                "symbol": "000858",
                "name": "五粮液",
                "market": "zh_a",
                "exchange": "SZ",
                "asset_type": "stock",
                "status": "active",
            },
        }
        symbols = kwargs.get("symbols") or []
        if symbols:
            return {symbol: payload[symbol] for symbol in symbols if symbol in payload}
        return payload

    def get_taxonomy_by_security(self, symbol: str):
        return [
            {
                "canonical_taxonomy": "sw",
                "canonical_level": 1,
                "canonical_category_code": "801120",
                "canonical_category_name": "食品饮料",
                "canonical_index_code": "801120.SI",
                "derived_flags": {"financial_sector": False},
            }
        ]

    def query_financial_statements(self, *, statement_type: str, **kwargs):
        symbol = kwargs.get("symbol", "000001")
        multiplier = {"000001": 1.0, "600519": 2.0, "000858": 1.5}.get(symbol, 1.0)
        security_name = {"000001": "测试股份", "600519": "贵州茅台", "000858": "五粮液"}.get(symbol, symbol)
        if statement_type == "income":
            return {
                "data": [
                    {
                        "symbol": symbol,
                        "market": "zh_a",
                        "security_name": security_name,
                        "reporting_period": "2025-12-31",
                        "ann_date": "2026-03-20",
                        "comp_type_code": 1,
                        "statement_code": "合并报表",
                        "report_type": "年报",
                        "data_json": {
                            "TOT_OPERA_REV": 12_000_000_000 * multiplier,
                            "OPERA_PROFIT": 1_500_000_000 * multiplier,
                            "TOTAL_PROFIT": 1_450_000_000 * multiplier,
                            "NET_PRO_EXCL_MIN_INT_INC": 1_000_000_000 * multiplier,
                            "TOT_OPERA_COST": 9_000_000_000 * multiplier,
                            "LESS_OPERA_COST": 8_000_000_000 * multiplier,
                            "LESS_SELLING_EXP": 300_000_000 * multiplier,
                            "LESS_ADMIN_EXP": 200_000_000 * multiplier,
                            "LESS_FIN_EXP": 100_000_000 * multiplier,
                            "RD_EXP": 240_000_000 * multiplier,
                            "EBIT": 1_650_000_000 * multiplier,
                            "EBITDA": 1_900_000_000 * multiplier,
                        },
                    },
                    {
                        "symbol": symbol,
                        "market": "zh_a",
                        "security_name": security_name,
                        "reporting_period": "2024-12-31",
                        "ann_date": "2025-03-20",
                        "comp_type_code": 1,
                        "data_json": {
                            "TOT_OPERA_REV": 10_000_000_000 * multiplier,
                            "OPERA_PROFIT": 1_200_000_000 * multiplier,
                            "TOTAL_PROFIT": 1_150_000_000 * multiplier,
                            "NET_PRO_EXCL_MIN_INT_INC": 900_000_000 * multiplier,
                            "TOT_OPERA_COST": 7_800_000_000 * multiplier,
                            "LESS_OPERA_COST": 7_000_000_000 * multiplier,
                            "LESS_SELLING_EXP": 260_000_000 * multiplier,
                            "LESS_ADMIN_EXP": 180_000_000 * multiplier,
                            "LESS_FIN_EXP": 90_000_000 * multiplier,
                            "RD_EXP": 200_000_000 * multiplier,
                            "EBIT": 1_300_000_000 * multiplier,
                            "EBITDA": 1_550_000_000 * multiplier,
                        },
                    },
                ]
            }
        if statement_type == "balance_sheet":
            return {
                "data": [
                    {
                        "symbol": symbol,
                        "market": "zh_a",
                        "security_name": security_name,
                        "reporting_period": "2025-12-31",
                        "ann_date": "2026-03-20",
                        "comp_type_code": 1,
                        "data_json": {
                            "TOTAL_ASSETS": 20_000_000_000 * multiplier,
                            "TOTAL_LIAB": 10_000_000_000 * multiplier,
                            "TOTAL_CUR_ASSETS": 8_000_000_000 * multiplier,
                            "TOTAL_CUR_LIAB": 4_000_000_000 * multiplier,
                            "TOT_SHARE_EQUITY_EXCL_MIN_INT": 10_000_000_000 * multiplier,
                            "INV": 1_000_000_000 * multiplier,
                            "ACCT_RECEIVABLE": 2_000_000_000 * multiplier,
                            "CURRENCY_CAP": 2_200_000_000 * multiplier,
                            "ST_BORROWING": 900_000_000 * multiplier,
                            "LT_LOAN": 2_100_000_000 * multiplier,
                            "BONDS_PAYABLE": 1_500_000_000 * multiplier,
                        },
                    },
                    {
                        "symbol": symbol,
                        "market": "zh_a",
                        "security_name": security_name,
                        "reporting_period": "2024-12-31",
                        "ann_date": "2025-03-20",
                        "comp_type_code": 1,
                        "data_json": {
                            "TOTAL_ASSETS": 18_000_000_000 * multiplier,
                            "TOTAL_LIAB": 9_500_000_000 * multiplier,
                            "TOTAL_CUR_ASSETS": 7_000_000_000 * multiplier,
                            "TOTAL_CUR_LIAB": 3_700_000_000 * multiplier,
                            "TOT_SHARE_EQUITY_EXCL_MIN_INT": 8_500_000_000 * multiplier,
                            "INV": 900_000_000 * multiplier,
                            "ACCT_RECEIVABLE": 1_800_000_000 * multiplier,
                            "CURRENCY_CAP": 2_000_000_000 * multiplier,
                            "ST_BORROWING": 700_000_000 * multiplier,
                            "LT_LOAN": 1_900_000_000 * multiplier,
                            "BONDS_PAYABLE": 1_200_000_000 * multiplier,
                        },
                    },
                ]
            }
        if statement_type == "cashflow":
            return {
                "data": [
                    {
                        "symbol": symbol,
                        "market": "zh_a",
                        "security_name": security_name,
                        "reporting_period": "2025-12-31",
                        "ann_date": "2026-03-20",
                        "comp_type_code": 1,
                        "data_json": {
                            "NET_CASH_FLOW_OPERA_ACT": 800_000_000 * multiplier,
                            "NET_CASH_FLOW_INV_ACT": -600_000_000 * multiplier,
                            "NET_CASH_FLOW_FIN_ACT": 300_000_000 * multiplier,
                            "FREE_CASH_FLOW": 200_000_000 * multiplier,
                            "CASH_PAID_PUR_CONST_FIOLTA": 500_000_000 * multiplier,
                            "CASH_RECP_SG_AND_RS": 11_500_000_000 * multiplier,
                            "NET_INCR_CASH_AND_CASH_EQU": 400_000_000 * multiplier,
                        },
                    },
                    {
                        "symbol": symbol,
                        "market": "zh_a",
                        "security_name": security_name,
                        "reporting_period": "2024-12-31",
                        "ann_date": "2025-03-20",
                        "comp_type_code": 1,
                        "data_json": {
                            "NET_CASH_FLOW_OPERA_ACT": 900_000_000 * multiplier,
                            "NET_CASH_FLOW_INV_ACT": -400_000_000 * multiplier,
                            "NET_CASH_FLOW_FIN_ACT": 200_000_000 * multiplier,
                            "FREE_CASH_FLOW": 250_000_000 * multiplier,
                            "CASH_PAID_PUR_CONST_FIOLTA": 450_000_000 * multiplier,
                            "CASH_RECP_SG_AND_RS": 9_600_000_000 * multiplier,
                            "NET_INCR_CASH_AND_CASH_EQU": 350_000_000 * multiplier,
                        },
                    },
                ]
            }
        return {"data": [], "total": 0}

    def query_industry_constituents_by_index(self, **kwargs):
        return {
            "list": [
                {"con_code": "000001"},
                {"con_code": "600519"},
                {"con_code": "000858"},
            ],
            "count": 3,
        }


def test_bi_service_dashboard_computes_core_metrics(monkeypatch):
    monkeypatch.setattr(BIService, "_build_phoenix_client", lambda self: FakePhoenixClient())
    svc = BIService()

    result = svc.get_company_dashboard(symbol="000001", as_of_date="2026-05-19")

    assert result.company.name == "测试股份"
    assert result.latest_period == "2025-12-31"
    assert len(result.kpis) == 8
    metric_map = {item.code: item for item in result.kpis}
    assert round(metric_map["revenue_total"].value or 0, 2) == 120.0
    assert round(metric_map["debt_ratio"].value or 0, 3) == 0.5
    assert round(metric_map["roe"].value or 0, 6) == round(1_000_000_000 / 9_250_000_000, 6)
    warning_codes = {item.code for item in result.warnings}
    assert "ocf_weaker_than_profit" in warning_codes


def test_bi_service_dupont_and_quality_have_phase1_structures(monkeypatch):
    monkeypatch.setattr(BIService, "_build_phoenix_client", lambda self: FakePhoenixClient())
    svc = BIService()

    dupont = svc.get_company_dupont(symbol="000001", as_of_date="2026-05-19")
    quality = svc.get_company_quality(symbol="000001", as_of_date="2026-05-19")
    metrics_meta = svc.get_metric_definitions()

    assert dupont.dupont_tree.code == "roe"
    assert {child.code for child in dupont.dupont_tree.children} == {"net_margin", "asset_turnover", "equity_multiplier"}
    assert len(dupont.driver_summary) >= 1
    assert [panel.code for panel in quality.panels] == ["operating_quality", "cashflow_quality", "turnover", "solvency"]
    metric_codes = {item.code for item in metrics_meta.metrics}
    assert "revenue_total" in metric_codes
    assert "equity_multiplier" in metric_codes


def test_bi_service_search_peer_comparison_and_insight(monkeypatch):
    monkeypatch.setattr(BIService, "_build_phoenix_client", lambda self: FakePhoenixClient())
    svc = BIService()

    search_result = svc.search_securities(query="茅台", market="zh_a", limit=10)
    assert search_result.total >= 1
    assert search_result.items[0].symbol == "600519"

    peer_result = svc.get_peer_comparison(
        req=BIPeerComparisonRequest(
            industry_code="801120.SI",
            as_of_date="2026-05-19",
            metrics=["revenue_total", "roe"],
            limit=3,
        )
    )
    assert len(peer_result.rows) == 3
    assert {row.symbol for row in peer_result.rows} == {"000001", "600519", "000858"}
    assert "revenue_total" in peer_result.rows[0].metrics

    insight = svc.get_company_insight(symbol="000001", as_of_date="2026-05-19")
    assert insight.headline
    assert len(insight.structured_highlights) >= 1
    assert len(insight.trend_summary) >= 1




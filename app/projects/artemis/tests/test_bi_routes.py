from fastapi import FastAPI
from fastapi.testclient import TestClient
import artemis.api.http_gateway.bi_routes as bi_routes_module
from artemis.models.bi import BICompanyMeta, BIDashboardResponse, BIIndustryMeta, BIInsightResponse, BIMetricDefinition, BIMetricsMetaResponse, BIPeerComparisonResponse, BISecuritySearchItem, BISecuritySearchResponse


class FakeRouteService:
    def get_company_dashboard(self, **kwargs):
        return BIDashboardResponse(
            symbol=kwargs["symbol"],
            as_of_date=kwargs["as_of_date"],
            latest_period="2025-12-31",
            company=BICompanyMeta(symbol=kwargs["symbol"], name="Test Corp", market="zh_a", exchange="SZ", industry=BIIndustryMeta(name="Food"), comp_type_code=1, financial_sector=False),
            kpis=[], trend_sections=[], summary_cards=[], warnings=[], source_notes=[]
        )
    def get_company_dupont(self, **kwargs):
        raise AssertionError("not used in this test")
    def get_company_quality(self, **kwargs):
        raise AssertionError("not used in this test")

    def search_securities(self, **kwargs):
        return BISecuritySearchResponse(query=kwargs["query"], market=kwargs.get("market", "zh_a"), total=1, items=[
            BISecuritySearchItem(symbol="000001", name="Test Corp", exchange="SZ", market="zh_a", asset_type="stock", status="active")
        ])

    def get_peer_comparison(self, req):
        return BIPeerComparisonResponse(as_of_date=req.as_of_date, market=req.market, industry_code=req.industry_code, requested_metrics=req.metrics or ["revenue_total"], rows=[])

    def get_company_insight(self, **kwargs):
        return BIInsightResponse(symbol=kwargs["symbol"], as_of_date=kwargs["as_of_date"], latest_period="2025-12-31", company=BICompanyMeta(symbol=kwargs["symbol"], name="Test Corp", market="zh_a", exchange="SZ", industry=BIIndustryMeta(name="Food"), comp_type_code=1, financial_sector=False), headline="structured headline", structured_highlights=[], anomalies=[], trend_summary=["summary line"], source_notes=[])

    def get_metric_definitions(self):
        return BIMetricsMetaResponse(version="v1", metrics=[
            BIMetricDefinition(code="revenue_total", label="Revenue", category="profitability", display_kind="amount", unit="亿元", formula="TOT_OPERA_REV", source_fields=["income.TOT_OPERA_REV"], applicable_comp_types=[1], phase="phase1", available=True)
        ])


def test_bi_routes_dashboard_and_metrics(monkeypatch):
    app = FastAPI()
    app.include_router(bi_routes_module.router)
    monkeypatch.setattr(bi_routes_module, "service", FakeRouteService())
    client = TestClient(app)
    dashboard_resp = client.get("/bi/financial/company/000001/dashboard", params={"as_of_date": "2026-05-19"})
    assert dashboard_resp.status_code == 200
    assert dashboard_resp.json()["company"]["name"] == "Test Corp"
    assert dashboard_resp.json()["latest_period"] == "2025-12-31"
    metrics_resp = client.get("/bi/meta/metrics")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["version"] == "v1"
    assert metrics_resp.json()["metrics"][0]["code"] == "revenue_total"

    search_resp = client.get("/bi/search/securities", params={"query": "000001"})
    assert search_resp.status_code == 200
    assert search_resp.json()["items"][0]["symbol"] == "000001"

    peer_resp = client.post("/bi/financial/peer-comparison", json={"symbols": ["000001", "600519"], "as_of_date": "2026-05-19", "market": "zh_a", "metrics": ["revenue_total"]})
    assert peer_resp.status_code == 200
    assert peer_resp.json()["requested_metrics"] == ["revenue_total"]

    insight_resp = client.get("/bi/financial/company/000001/insight", params={"as_of_date": "2026-05-19"})
    assert insight_resp.status_code == 200
    assert insight_resp.json()["headline"] == "structured headline"


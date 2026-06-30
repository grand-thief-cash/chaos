from fastapi import FastAPI
from fastapi.testclient import TestClient

from artemis.api.http_gateway.factor_routes import router
from artemis.services import factor_service


def _sample_capabilities_payload() -> dict:
    return {
        "capabilities": [
            {
                "domain": "bars",
                "tables": [
                    {
                        "table_name": "bars_stock_daily",
                        "data_sources": [{"source": "baostock", "row_count": 100}],
                        "time_range": {"min_date": "2024-01-01", "max_date": "2026-05-14"},
                        "capability": {
                            "output_fields": [
                                {"name": "trade_date"},
                                {"name": "close"},
                            ],
                        },
                    },
                ],
            },
            {
                "domain": "financial",
                "tables": [
                    {
                        "table_name": "financial_statement",
                        "data_sources": [{"source": "amazing_data", "row_count": 200}],
                        "time_range": {"min_date": "2010-01-01", "max_date": "2026-03-31"},
                        "capability": {
                            "data_types": [
                                {"type_value": "income"},
                                {"type_value": "balance_sheet"},
                                {"type_value": "cashflow"},
                            ],
                            "output_fields": [
                                {"name": "symbol"},
                                {"name": "reporting_period"},
                                {"name": "data_json"},
                            ],
                        },
                    },
                    {
                        "table_name": "corporate_action",
                        "data_sources": [{"source": "amazing_data", "row_count": 50}],
                        "time_range": {"min_date": "2015-01-01", "max_date": "2026-05-01"},
                        "capability": {
                            "data_types": [
                                {"type_value": "dividend"},
                            ],
                            "output_fields": [
                                {"name": "symbol"},
                                {"name": "report_period"},
                                {"name": "data_json"},
                            ],
                        },
                    },
                ],
            },
        ],
    }


def test_factor_service_availability_uses_capabilities(monkeypatch):
    monkeypatch.setattr(factor_service, "_get_catalog_capabilities", lambda refresh=False, source=None: _sample_capabilities_payload())

    result = factor_service.get_availability(refresh=True)

    assert result["capability_source"] == "phoenixA_catalog"
    assert result["summary"]["available"] > 0
    items = {item["name"]: item for item in result["factors"]}
    assert items["dividend_yield"]["availability_status"] == "available"
    assert "corporate_action.dividend.data_json.DVD_PER_SHARE_PRE_TAX_CASH" in items["dividend_yield"]["required_fields"]
    assert items["roe"]["source_status"]["income"]["available"] is True


def test_factor_service_availability_marks_missing_sources(monkeypatch):
    payload = _sample_capabilities_payload()
    payload["capabilities"][1]["tables"] = [payload["capabilities"][1]["tables"][0]]  # remove corporate_action
    monkeypatch.setattr(factor_service, "_get_catalog_capabilities", lambda refresh=False, source=None: payload)

    result = factor_service.get_availability()
    items = {item["name"]: item for item in result["factors"]}

    assert items["dividend_yield"]["availability_status"] == "partial"
    assert "corporate_action" in items["dividend_yield"]["missing_sources"]
    assert any(note.startswith("missing_sources:") for note in items["dividend_yield"]["notes"])


def test_factor_availability_route(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(factor_service, "get_availability", lambda refresh=False, source=None: {"refresh": refresh, "source": source, "factors": []})

    client = TestClient(app)
    response = client.get("/factors/availability", params={"refresh": "true", "source": "home"})

    assert response.status_code == 200
    assert response.json() == {"refresh": True, "source": "home", "factors": []}


def test_factor_service_availability_marks_unreachable_capabilities_as_unknown(monkeypatch):
    monkeypatch.setattr(
        factor_service,
        "_get_catalog_capabilities",
        lambda refresh=False, source=None: {"capabilities": [], "_reachable": False, "_error": "connection refused"},
    )

    result = factor_service.get_availability()

    assert result["capability_source"] == "unavailable"
    assert result["capability_error"] == "connection refused"
    assert result["source_status"]["bars"]["status"] == "unknown"
    items = {item["name"]: item for item in result["factors"]}
    assert items["dividend_yield"]["availability_status"] == "unknown"


def test_factor_service_availability_detects_missing_required_fields(monkeypatch):
    payload = {
        "_reachable": True,
        "capabilities": [
            {
                "domain": "bars",
                "tables": [
                    {
                        "table_name": "bars_stock_zh_a_daily_nf",
                        "row_count": 10,
                        "data_sources": [{"source": "baostock", "row_count": 10}],
                        "capability": {"output_fields": [{"name": "trade_date"}, {"name": "close"}]},
                    }
                ],
            },
            {
                "domain": "financial",
                "tables": [
                    {
                        "table_name": "corporate_action",
                        "row_count": 10,
                        "data_sources": [{"source": "amazing_data", "row_count": 10}],
                        "capability": {
                            "data_types": [{"type_value": "dividend"}],
                            "output_fields": [{"name": "symbol"}, {"name": "ann_date"}],
                        },
                    },
                ],
            },
        ],
    }
    monkeypatch.setattr(factor_service, "_get_catalog_capabilities", lambda refresh=False, source=None: payload)

    result = factor_service.get_availability()

    items = {item["name"]: item for item in result["factors"]}
    dividend_yield = items["dividend_yield"]
    assert dividend_yield["availability_status"] == "partial"
    assert "corporate_action.dividend.data_json.DVD_PER_SHARE_PRE_TAX_CASH" in dividend_yield["missing_fields"]
    assert any(note.startswith("missing_required_fields:") for note in dividend_yield["notes"])



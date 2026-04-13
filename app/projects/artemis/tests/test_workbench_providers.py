from __future__ import annotations


import pytest

from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.models.workbench import MarketDataQuery
from artemis.services.workbench.market_data import get_market_bars
from artemis.services.workbench.providers import (
    PhoenixIndexZhAProvider,
    PhoenixStockZhAProvider,
    provider_registry,
)


class FakeStockClient:
    def __init__(self):
        self.calls = []

    def get_stock_zh_a_hist_bars(self, **kwargs):
        self.calls.append(kwargs)
        return [{"date": "2024-01-02", "code": kwargs["symbol"], "close": 10.0}]


class FakeIndexClient:
    def get_index_zh_a_hist_bars(self, **kwargs):
        raise NotImplementedError("missing index endpoint")


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = "payload"

    def json(self):
        return self._payload


def test_provider_registry_resolves_stock_and_index_providers():
    stock_provider = provider_registry.resolve(asset_type="stock", market="zh_a")
    index_provider = provider_registry.resolve(asset_type="index", market="zh_a")

    assert isinstance(stock_provider, PhoenixStockZhAProvider)
    assert isinstance(index_provider, PhoenixIndexZhAProvider)


def test_provider_registry_rejects_unsupported_combination():
    with pytest.raises(ValueError, match="asset_type=crypto, market=us"):
        provider_registry.resolve(asset_type="crypto", market="us")


def test_stock_provider_maps_query_to_phoenix_stock_api():
    provider = PhoenixStockZhAProvider()
    client = FakeStockClient()
    query = MarketDataQuery(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-01-31",
        asset_type="stock",
        market="zh_a",
        period="weekly",
        adjust="qfq",
    )

    bars = provider.fetch_bars(client=client, query=query)

    assert bars[0]["code"] == "000001"
    assert client.calls[0]["timeframe"] == "weekly"
    assert client.calls[0]["adjust"] == "qfq"


def test_index_provider_surfaces_clear_error_for_missing_endpoint():
    provider = PhoenixIndexZhAProvider()
    query = MarketDataQuery(
        symbol="000300",
        start_date="2024-01-01",
        end_date="2024-01-31",
        asset_type="index",
        market="zh_a",
        period="daily",
        adjust="nf",
    )

    with pytest.raises(ValueError, match="index history endpoint is not implemented yet"):
        provider.fetch_bars(client=FakeIndexClient(), query=query)


def test_market_data_index_request_returns_clear_validation_error(monkeypatch):
    monkeypatch.setattr(
        "artemis.services.workbench.market_data._build_phoenix_client",
        lambda source=None: FakeIndexClient(),
    )

    with pytest.raises(ValueError, match="asset_type=index, market=zh_a"):
        get_market_bars(
            symbol="000300",
            start_date="2024-01-01",
            end_date="2024-01-31",
            period="weekly",
            adjust="",
            asset_type="index",
            market="zh_a",
            source="production",
            use_cache=False,
        )


def test_phoenix_stock_client_paginates_until_last_page(monkeypatch):
    client = PhoenixAClient(host="127.0.0.1", port=8080)
    offsets = []

    def fake_get(path, params=None, headers=None):
        offsets.append(params["offset"])
        if params["offset"] == 0:
            return FakeResponse(200, {"data": [
                {"date": "2024-01-02", "code": "000001"},
                {"date": "2024-01-03", "code": "000001"},
            ]})
        return FakeResponse(200, {"data": [
            {"date": "2024-01-04", "code": "000001"},
        ]})

    monkeypatch.setattr(client, "get", fake_get)

    rows = client.get_stock_zh_a_hist_bars(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-01-31",
        timeframe="daily",
        adjust="nf",
        limit=2,
    )

    assert [row["date"] for row in rows] == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert offsets == [0, 2]


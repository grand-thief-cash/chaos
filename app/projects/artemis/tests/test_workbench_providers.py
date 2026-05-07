from __future__ import annotations


import pytest

from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.models.workbench import MarketDataQuery
from artemis.services.workbench.market_data import get_market_bars
from artemis.services.workbench.providers import (
    PhoenixBarsProvider,
    PhoenixStockZhAProvider,
    PhoenixIndexZhAProvider,
    provider_registry,
)


class FakeStockClient:
    """Fake client implementing get_bars() for stock asset type."""

    def __init__(self):
        self.calls = []

    def get_bars(self, **kwargs):
        self.calls.append(kwargs)
        # get_bars with normalize_for_cache=True returns date/code (CacheEngine format)
        return [{"date": "2024-01-02", "code": kwargs["symbol"], "close": 10.0}]


class FakeIndexClient:
    """Fake client implementing get_bars() for index asset type."""

    def __init__(self):
        self.calls = []

    def get_bars(self, **kwargs):
        self.calls.append(kwargs)
        return [{"date": "2024-01-02", "code": kwargs["symbol"], "close": 3000.0}]


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

    # Both resolve to the unified PhoenixBarsProvider
    assert isinstance(stock_provider, PhoenixBarsProvider)
    assert isinstance(index_provider, PhoenixBarsProvider)


def test_legacy_aliases_point_to_phoenix_bars_provider():
    """PhoenixStockZhAProvider and PhoenixIndexZhAProvider are aliases for PhoenixBarsProvider."""
    assert PhoenixStockZhAProvider is PhoenixBarsProvider
    assert PhoenixIndexZhAProvider is PhoenixBarsProvider


def test_provider_supports_all_asset_types():
    """PhoenixBarsProvider.supports() returns True for all asset_type/market combos."""
    provider = PhoenixBarsProvider()
    assert provider.supports(asset_type="stock", market="zh_a")
    assert provider.supports(asset_type="index", market="zh_a")
    assert provider.supports(asset_type="crypto", market="us")


def test_stock_provider_maps_query_to_phoenix_bars_api():
    provider = PhoenixBarsProvider()
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

    # get_bars with normalize_for_cache=True returns CacheEngine format (code/date)
    assert bars[0]["code"] == "000001"
    assert client.calls[0]["period"] == "weekly"
    assert client.calls[0]["adjust"] == "qfq"
    assert client.calls[0]["asset_type"] == "stock"
    assert client.calls[0]["market"] == "zh_a"
    assert client.calls[0]["normalize_for_cache"] is True


def test_index_provider_uses_same_get_bars_api():
    """Index queries also go through PhoenixBarsProvider → client.get_bars()."""
    provider = PhoenixBarsProvider()
    client = FakeIndexClient()
    query = MarketDataQuery(
        symbol="000300",
        start_date="2024-01-01",
        end_date="2024-01-31",
        asset_type="index",
        market="zh_a",
        period="daily",
        adjust="nf",
    )

    bars = provider.fetch_bars(client=client, query=query)

    assert bars[0]["code"] == "000300"
    assert client.calls[0]["asset_type"] == "index"
    assert client.calls[0]["market"] == "zh_a"
    assert client.calls[0]["period"] == "daily"


def test_market_data_service_delegates_to_phoenix_bars_provider(monkeypatch):
    """get_market_bars() routes through PhoenixBarsProvider for index data."""
    fake_client = FakeIndexClient()
    monkeypatch.setattr(
        "artemis.services.workbench.market_data._build_phoenix_client",
        lambda source=None: fake_client,
    )

    result = get_market_bars(
        symbol="000300",
        start_date="2024-01-01",
        end_date="2024-01-31",
        period="weekly",
        adjust="nf",
        asset_type="index",
        market="zh_a",
        source="production",
        use_cache=False,
    )

    assert result["symbol"] == "000300"
    assert result["period"] == "weekly"
    assert len(result["bars"]) == 1
    assert fake_client.calls[0]["asset_type"] == "index"


def test_phoenix_stock_client_paginates_until_last_page(monkeypatch):
    client = PhoenixAClient(host="127.0.0.1", port=8080)
    offsets = []

    def fake_get(path, params=None, headers=None):
        offsets.append(params["offset"])
        if params["offset"] == 0:
            return FakeResponse(200, {"data": [
                {"trade_date": "2024-01-02", "symbol": "000001"},
                {"trade_date": "2024-01-03", "symbol": "000001"},
            ]})
        return FakeResponse(200, {"data": [
            {"trade_date": "2024-01-04", "symbol": "000001"},
        ]})

    monkeypatch.setattr(client, "get", fake_get)

    # Use v2 API directly: get_bars with normalize_for_cache=True
    rows = client.get_bars(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-01-31",
        period="daily",
        adjust="nf",
        limit=2,
        normalize_for_cache=True,
    )

    # normalize_for_cache renames trade_date→date, symbol→code
    assert [row["date"] for row in rows] == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert offsets == [0, 2]


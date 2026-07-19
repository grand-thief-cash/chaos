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
    """Fake client implementing get_bars() / get_security_by_id() for stock asset type."""

    def __init__(self):
        self.calls = []

    def get_bars(self, **kwargs):
        self.calls.append(kwargs)
        return [{"date": "2024-01-02", "code": str(kwargs["security_id"]), "close": 10.0}]

    def get_security_by_id(self, security_id):
        return {1: {"security_id": 1, "symbol": "000001", "exchange": "SZ",
                    "asset_type": "stock", "market": "zh_a"}}.get(security_id)


class FakeIndexClient:
    """Fake client implementing get_bars() / get_security_by_id() for index asset type."""

    def __init__(self):
        self.calls = []

    def get_bars(self, **kwargs):
        self.calls.append(kwargs)
        return [{"date": "2024-01-02", "code": str(kwargs["security_id"]), "close": 3000.0}]

    def get_security_by_id(self, security_id):
        return {3: {"security_id": 3, "symbol": "000300", "exchange": "SH",
                    "asset_type": "index", "market": "zh_a"}}.get(security_id)


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
        security_id=1,
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
    assert bars[0]["code"] == "1"
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
        security_id=3,
        symbol="000300",
        start_date="2024-01-01",
        end_date="2024-01-31",
        asset_type="index",
        market="zh_a",
        period="daily",
        adjust="nf",
    )

    bars = provider.fetch_bars(client=client, query=query)

    assert bars[0]["code"] == "3"
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
        security_id=3,
        start_date="2024-01-01",
        end_date="2024-01-31",
        period="weekly",
        adjust="nf",
        asset_type="index",
        market="zh_a",
        source="production",
        use_cache=False,
    )

    assert result["security_id"] == 3
    assert result["symbol"] == "000300"
    assert result["period"] == "weekly"
    assert len(result["bars"]) == 1
    assert fake_client.calls[0]["asset_type"] == "index"


def test_market_data_rejects_asset_type_mismatch(monkeypatch):
    """A security_id whose registry asset_type doesn't match the request must
    raise — otherwise cache_engine would route to the wrong (asset_type, market)
    bucket and silently return the wrong security's bars."""
    fake_client = FakeIndexClient()
    monkeypatch.setattr(
        "artemis.services.workbench.market_data._build_phoenix_client",
        lambda source=None: fake_client,
    )
    import pytest as _pytest
    with _pytest.raises(ValueError, match="asset_type mismatch"):
        get_market_bars(
            security_id=3,  # registry says index
            start_date="2024-01-01",
            end_date="2024-01-31",
            period="weekly",
            adjust="nf",
            asset_type="stock",  # request says stock — mismatch
            market="zh_a",
            use_cache=False,
        )
    # Must not have fetched bars (fail-closed before provider call).
    assert fake_client.calls == []


def test_market_data_rejects_security_id_not_found(monkeypatch):
    """An unknown security_id raises ValueError (→ 400), not a silent empty result."""
    fake_client = FakeIndexClient()
    monkeypatch.setattr(
        "artemis.services.workbench.market_data._build_phoenix_client",
        lambda source=None: fake_client,
    )
    import pytest as _pytest
    with _pytest.raises(ValueError, match="not found"):
        get_market_bars(
            security_id=999,  # not in the fake registry
            start_date="2024-01-01",
            end_date="2024-01-31",
            asset_type="index",
            market="zh_a",
            use_cache=False,
        )


def test_market_data_normalizes_asset_type_before_resolve(monkeypatch):
    """Whitespace in asset_type/market is normalized BEFORE the registry compare,
    so a direct API call with " stock " / "zh_a " is not falsely rejected as a
    mismatch (the registry stores stripped values)."""
    fake_client = FakeStockClient()
    monkeypatch.setattr(
        "artemis.services.workbench.market_data._build_phoenix_client",
        lambda source=None: fake_client,
    )
    result = get_market_bars(
        security_id=1,
        start_date="2024-01-01",
        end_date="2024-01-31",
        asset_type=" stock ",  # whitespace — would falsely mismatch without normalize
        market=" zh_a ",
        use_cache=False,
    )
    assert result["security_id"] == 1
    assert result["symbol"] == "000001"
    assert fake_client.calls[0]["asset_type"] == "stock"  # normalized on the wire


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

    rows = client.get_bars(
        security_id=1,
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

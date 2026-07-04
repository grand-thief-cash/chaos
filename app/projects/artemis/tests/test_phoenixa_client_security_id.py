"""Unit tests for PhoenixAClient Phase 3 security_id resolve behavior."""
from unittest.mock import MagicMock

import pytest

from artemis.core.clients.phoenixA_client import PhoenixAClient


def _make_client() -> PhoenixAClient:
    """A PhoenixAClient with no real HTTP backend; get_securities is mocked."""
    return PhoenixAClient(host="localhost", port=9999, logger=None)


def test_explicit_security_id_passes_through():
    client = _make_client()
    params = client.security_id_query_params(
        security_id=5, security_ids=None, symbol="", symbols=None,
        exchange=None, asset_type="stock", market="zh_a",
    )
    assert params == {"security_id": "5"}


def test_no_identity_returns_empty():
    """No identity supplied → {} (unfiltered is intentional)."""
    client = _make_client()
    client.get_securities = MagicMock(return_value={})
    params = client.security_id_query_params(
        security_id=None, security_ids=None, symbol="", symbols=None,
        exchange=None, asset_type="stock", market="zh_a",
    )
    assert params == {}


def test_symbol_resolved_to_security_id():
    client = _make_client()
    client.get_securities = MagicMock(return_value={
        "000001": {"symbol": "000001", "exchange": "SZ", "security_id": 42},
    })
    params = client.security_id_query_params(
        security_id=None, security_ids=None, symbol="000001", symbols=None,
        exchange="SZ", asset_type="stock", market="zh_a",
    )
    assert params == {"security_id": "42"}


def test_unresolved_symbol_raises():
    """Symbol supplied but not in registry → must raise, NOT degrade to an
    unfiltered query (which would return unrelated data)."""
    client = _make_client()
    client.get_securities = MagicMock(return_value={})
    with pytest.raises(ValueError):
        client.security_id_query_params(
            security_id=None, security_ids=None, symbol="000001", symbols=None,
            exchange="SZ", asset_type="stock", market="zh_a",
        )


def test_unresolved_symbols_list_raises():
    client = _make_client()
    client.get_securities = MagicMock(return_value={})
    with pytest.raises(ValueError):
        client.security_id_query_params(
            security_id=None, security_ids=None, symbol="", symbols=["000001", "600519"],
            exchange=None, asset_type="stock", market="zh_a",
        )


def test_query_method_returns_empty_on_resolve_failure():
    """Query methods must catch the resolve ValueError and return empty (so
    factor_engine degrades gracefully instead of crashing)."""
    client = _make_client()
    client.get_securities = MagicMock(return_value={})
    # symbol "000001" not in registry → resolve raises → method returns empty.
    result = client.query_financial_statements(
        source="amazing_data", statement_type="balance_sheet", symbol="000001",
    )
    assert result == {"data": [], "total": 0}


def test_explicit_security_id_zero_raises():
    """security_id=0 is supplied-but-invalid (not 'not supplied') → must raise,
    not degrade to an unfiltered query."""
    client = _make_client()
    with pytest.raises(ValueError):
        client.security_id_query_params(
            security_id=0, security_ids=None, symbol="", symbols=None,
            exchange=None, asset_type="stock", market="zh_a",
        )


def test_security_ids_with_zero_raises():
    client = _make_client()
    with pytest.raises(ValueError):
        client.security_id_query_params(
            security_id=None, security_ids=[1, 0, 2], symbol="", symbols=None,
            exchange=None, asset_type="stock", market="zh_a",
        )


def test_partial_symbols_raises():
    """If some symbols in a batch resolve and others don't, must raise — never
    silently query only the resolved subset (caller would miss the rest)."""
    client = _make_client()
    client.get_securities = MagicMock(return_value={
        "000001": {"symbol": "000001", "exchange": "SZ", "security_id": 42},
        # "BAD" not in registry
    })
    with pytest.raises(ValueError):
        client.security_id_query_params(
            security_id=None, security_ids=None, symbol="", symbols=["000001", "BAD"],
            exchange=None, asset_type="stock", market="zh_a",
        )


def test_security_id_zero_query_returns_empty():
    """A query with security_id=0 must return empty (caught ValueError), not an
    unfiltered query."""
    client = _make_client()
    result = client.query_financial_statements(
        source="amazing_data", statement_type="balance_sheet", security_id=0,
    )
    assert result == {"data": [], "total": 0}


def test_empty_security_ids_list_raises():
    """An explicit security_ids=[] is supplied-but-empty → must raise (not
    degrade to an unfiltered query)."""
    client = _make_client()
    with pytest.raises(ValueError):
        client.security_id_query_params(
            security_id=None, security_ids=[], symbol="", symbols=None,
            exchange=None, asset_type="stock", market="zh_a",
        )


def test_empty_symbols_list_raises():
    """An explicit symbols=[] is supplied-but-empty → must raise."""
    client = _make_client()
    with pytest.raises(ValueError):
        client.security_id_query_params(
            security_id=None, security_ids=None, symbol="", symbols=[],
            exchange=None, asset_type="stock", market="zh_a",
        )


def test_empty_security_ids_query_returns_empty():
    """query with security_ids=[] returns empty (caught), not unfiltered."""
    client = _make_client()
    result = client.query_financial_statements(
        source="amazing_data", statement_type="balance_sheet", security_ids=[],
    )
    assert result == {"data": [], "total": 0}

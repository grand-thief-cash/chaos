"""Unit tests for PhoenixAClient security_id params (security_id-only, no symbol convenience)."""
import pytest

from artemis.core.clients.phoenixA_client import PhoenixAClient


def _make_client() -> PhoenixAClient:
    """A PhoenixAClient with no real HTTP backend."""
    return PhoenixAClient(host="localhost", port=9999, logger=None)


def test_explicit_security_id_passes_through():
    client = _make_client()
    params = client._build_security_id_params(security_id=5, security_ids=None)
    assert params == {"security_id": "5"}


def test_no_identity_returns_empty():
    """No identity supplied → {} (unfiltered is intentional)."""
    client = _make_client()
    params = client._build_security_id_params(security_id=None, security_ids=None)
    assert params == {}


def test_explicit_security_id_zero_raises():
    """security_id=0 is supplied-but-invalid (not 'not supplied') → must raise,
    not degrade to an unfiltered query."""
    client = _make_client()
    with pytest.raises(ValueError):
        client._build_security_id_params(security_id=0, security_ids=None)


def test_security_ids_with_zero_raises():
    client = _make_client()
    with pytest.raises(ValueError):
        client._build_security_id_params(security_id=None, security_ids=[1, 0, 2])


def test_empty_security_ids_list_raises():
    """An explicit security_ids=[] is supplied-but-empty → must raise (not
    degrade to an unfiltered query)."""
    client = _make_client()
    with pytest.raises(ValueError):
        client._build_security_id_params(security_id=None, security_ids=[])


def test_multiple_security_ids_returns_csv():
    client = _make_client()
    params = client._build_security_id_params(security_id=None, security_ids=[1, 2, 3])
    assert params == {"security_ids": "1,2,3"}


def test_security_id_zero_query_returns_empty():
    """A query with security_id=0 must return empty (caught ValueError), not an
    unfiltered query."""
    client = _make_client()
    result = client.query_financial_statements(
        source="amazing_data", statement_type="balance_sheet", security_id=0,
    )
    assert result == {"data": [], "total": 0}


def test_empty_security_ids_query_returns_empty():
    """query with security_ids=[] returns empty (caught), not unfiltered."""
    client = _make_client()
    result = client.query_financial_statements(
        source="amazing_data", statement_type="balance_sheet", security_ids=[],
    )
    assert result == {"data": [], "total": 0}


# ── get_security_by_id error semantics ──
# A 5xx / network failure must NOT be masked as "not found" (which would surface
# as a 400 user error). Only a real 404 returns None.


class _FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "body"

    def json(self):
        return self._payload


def test_get_security_by_id_404_returns_none():
    client = _make_client()
    client.get = lambda path, params=None: _FakeResp(404)
    assert client.get_security_by_id(42) is None


def test_get_security_by_id_5xx_raises_runtime_error():
    """A 5xx response must raise (→500), not return None (which would mask as 404/400)."""
    client = _make_client()
    client.get = lambda path, params=None: _FakeResp(500)
    with pytest.raises(RuntimeError, match="failed: status 500"):
        client.get_security_by_id(42)


def test_get_security_by_id_network_error_re_raises():
    """A network exception from self.get() must propagate (→500), not be swallowed."""
    client = _make_client()

    def _boom(path, params=None):
        raise ConnectionError("phoenixA unreachable")

    client.get = _boom
    with pytest.raises(ConnectionError, match="phoenixA unreachable"):
        client.get_security_by_id(42)


def test_get_security_by_id_2xx_returns_data():
    client = _make_client()
    client.get = lambda path, params=None: _FakeResp(200, {"data": {"security_id": 42, "symbol": "000001"}})
    info = client.get_security_by_id(42)
    assert info == {"security_id": 42, "symbol": "000001"}

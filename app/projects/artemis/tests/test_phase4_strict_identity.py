"""Phase 4 strict-identity tests (refactor §3.6 / §8.bis-5).

Verifies that explicit-but-bad identity (empty / partial / unresolvable /
non-positive) raises → 400 at the boundary, never silently degrades to a
subset compute or an unfiltered query. Covers the GLM review fixes.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from artemis.services import factor_service
from artemis.api.http_gateway import bi_routes, factor_routes


def _mock_client(resolved_map):
    """Mock PhoenixAClient whose resolve_security_ids mirrors the real (silent-skip) behavior."""
    client = MagicMock()

    def resolve_security_ids(*, symbols, **kwargs):
        return [resolved_map[s] for s in symbols if s in resolved_map]

    client.resolve_security_ids = resolve_security_ids
    return client


class TestFactorServiceStrictResolve:
    def test_partial_symbol_batch_raises(self, monkeypatch):
        monkeypatch.setattr(factor_service, "_get_client", lambda source=None: _mock_client({"000001": 1}))
        with pytest.raises(ValueError, match="could not resolve all"):
            factor_service._resolve_security_ids(["000001", "BAD"], source=None)

    def test_all_miss_raises(self, monkeypatch):
        monkeypatch.setattr(factor_service, "_get_client", lambda source=None: _mock_client({}))
        with pytest.raises(ValueError, match="could not resolve all"):
            factor_service._resolve_security_ids(["BAD"], source=None)

    def test_client_unavailable_raises(self, monkeypatch):
        monkeypatch.setattr(factor_service, "_get_client", lambda source=None: None)
        with pytest.raises(ValueError, match="client unavailable"):
            factor_service._resolve_security_ids(["000001"], source=None)

    def test_empty_symbols_raises(self):
        with pytest.raises(ValueError, match="no non-empty symbols"):
            factor_service._resolve_security_ids([""], source=None)

    def test_full_resolve_succeeds(self, monkeypatch):
        monkeypatch.setattr(factor_service, "_get_client", lambda source=None: _mock_client({"000001": 1, "600000": 2}))
        assert factor_service._resolve_security_ids(["000001", "600000"], source=None) == [1, 2]


class TestComputeIncrementalValidation:
    def test_empty_security_ids_raises(self):
        with pytest.raises(ValueError, match="security_ids is empty"):
            factor_service.compute_incremental(security_ids=[], as_of_date="20250101")

    def test_non_positive_security_id_raises(self):
        with pytest.raises(ValueError, match="positive"):
            factor_service.compute_incremental(security_ids=[1, 0], as_of_date="20250101")

    def test_negative_security_id_raises(self):
        with pytest.raises(ValueError, match="positive"):
            factor_service.compute_incremental(security_ids=[-1], as_of_date="20250101")

    def test_no_identity_raises(self):
        with pytest.raises(ValueError, match="requires security_ids or symbols"):
            factor_service.compute_incremental(as_of_date="20250101")

    def test_partial_symbols_raises(self, monkeypatch):
        # Real resolve_security_ids silently skips unresolved symbols; factor_service
        # must surface that as a ValueError instead of computing a subset.
        monkeypatch.setattr(factor_service, "_get_client", lambda source=None: _mock_client({"000001": 1}))
        with pytest.raises(ValueError, match="could not resolve all"):
            factor_service.compute_incremental(symbols=["000001", "BAD"], as_of_date="20250101")


class TestGetSnapshotValidation:
    def test_zero_security_id_raises(self):
        with pytest.raises(ValueError, match="positive"):
            factor_service.get_snapshot(security_id=0, as_of_date="20250101")

    def test_negative_security_id_raises(self):
        with pytest.raises(ValueError, match="positive"):
            factor_service.get_snapshot(security_id=-5, as_of_date="20250101")


class TestBiParseIntList:
    def test_absent_returns_none(self):
        assert bi_routes._parse_int_list(None) is None

    def test_valid_list(self):
        assert bi_routes._parse_int_list("1,2,3") == [1, 2, 3]

    def test_single(self):
        assert bi_routes._parse_int_list("42") == [42]

    def test_empty_token_consecutive_comma_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_int_list("1,,2")
        assert exc.value.status_code == 400

    def test_present_empty_raises_400(self):
        # ?security_ids= → "" → must NOT become None (would degrade to unfiltered)
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_int_list("")
        assert exc.value.status_code == 400

    def test_leading_trailing_comma_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_int_list(",1,2,")
        assert exc.value.status_code == 400

    def test_non_numeric_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_int_list("1,abc,2")
        assert exc.value.status_code == 400

    def test_zero_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_int_list("1,0,2")
        assert exc.value.status_code == 400

    def test_negative_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_int_list("-1")
        assert exc.value.status_code == 400


class TestBiParseSecurityId:
    """Singular security_id query param → 400 (not FastAPI 422) on bad input.

    Mirrors `_parse_int_list` so both identity shapes return a uniform 400 +
    `{"detail": "..."}` envelope (GLM review P2/P3).
    """

    def test_absent_returns_none(self):
        assert bi_routes._parse_security_id(None) is None

    def test_valid(self):
        assert bi_routes._parse_security_id("5") == 5

    def test_whitespace_trimmed(self):
        assert bi_routes._parse_security_id("  5  ") == 5

    def test_empty_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_security_id("")
        assert exc.value.status_code == 400

    def test_zero_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_security_id("0")
        assert exc.value.status_code == 400

    def test_negative_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_security_id("-1")
        assert exc.value.status_code == 400

    def test_non_numeric_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            bi_routes._parse_security_id("abc")
        assert exc.value.status_code == 400


class TestFactorParseSecurityId:
    """factor /snapshot singular security_id → 400 (not 422) on bad input."""

    def test_absent_returns_none(self):
        assert factor_routes._parse_security_id(None) is None

    def test_valid(self):
        assert factor_routes._parse_security_id("42") == 42

    def test_empty_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            factor_routes._parse_security_id("")
        assert exc.value.status_code == 400

    def test_zero_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            factor_routes._parse_security_id("0")
        assert exc.value.status_code == 400

    def test_negative_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            factor_routes._parse_security_id("-1")
        assert exc.value.status_code == 400

    def test_non_numeric_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            factor_routes._parse_security_id("xyz")
        assert exc.value.status_code == 400


class TestBiSecurityIdParamsStrict:
    """BI `_security_id_params`: symbol/symbols convenience input is strict —
    explicit empty / empty-token → ValueError (→ 400 at the route), never
    treated as 'no identity' (which would degrade to an unfiltered query).
    Covers GLM review P1 (the symbol/symbols path was previously truthy-checked
    and silently dropped empty tokens)."""

    def _service(self):
        # bi_routes.service is a BIService() instance; _client() is lazy so
        # constructing it does not touch phoenixA.
        return bi_routes.service

    def _mock_client(self):
        client = MagicMock()
        client.security_id_query_params = MagicMock(return_value={"_sentinel": True})
        return client

    def test_empty_symbol_raises(self):
        client = self._mock_client()
        with pytest.raises(ValueError, match="symbol is empty"):
            self._service()._security_id_params(
                client, security_id=None, security_ids=None,
                symbol="", symbols=None, market="zh_a",
            )
        client.security_id_query_params.assert_not_called()

    def test_whitespace_symbol_raises(self):
        client = self._mock_client()
        with pytest.raises(ValueError, match="symbol is empty"):
            self._service()._security_id_params(
                client, security_id=None, security_ids=None,
                symbol="   ", symbols=None, market="zh_a",
            )

    def test_symbols_string_empty_token_raises(self):
        # ?symbols=,000001, — leading/trailing comma used to be silently stripped.
        client = self._mock_client()
        with pytest.raises(ValueError, match="empty token"):
            self._service()._security_id_params(
                client, security_id=None, security_ids=None,
                symbol=None, symbols=",000001,", market="zh_a",
            )

    def test_symbols_string_bare_empty_raises(self):
        # ?symbols= — empty string used to be truthy-false → treated as no identity.
        client = self._mock_client()
        with pytest.raises(ValueError, match="empty token"):
            self._service()._security_id_params(
                client, security_id=None, security_ids=None,
                symbol=None, symbols="", market="zh_a",
            )

    def test_symbols_list_empty_token_raises(self):
        client = self._mock_client()
        with pytest.raises(ValueError, match="empty token"):
            self._service()._security_id_params(
                client, security_id=None, security_ids=None,
                symbol=None, symbols=["000001", ""], market="zh_a",
            )

    def test_symbols_list_empty_raises(self):
        client = self._mock_client()
        with pytest.raises(ValueError, match="symbols is empty"):
            self._service()._security_id_params(
                client, security_id=None, security_ids=None,
                symbol=None, symbols=[], market="zh_a",
            )

    def test_valid_symbol_resolves(self):
        client = self._mock_client()
        self._service()._security_id_params(
            client, security_id=None, security_ids=None,
            symbol="000001", symbols=None, market="zh_a",
        )
        client.security_id_query_params.assert_called_once()
        _, kwargs = client.security_id_query_params.call_args
        assert kwargs["symbol"] == "000001"
        assert kwargs["symbols"] is None

    def test_valid_symbols_list_resolves(self):
        client = self._mock_client()
        self._service()._security_id_params(
            client, security_id=None, security_ids=None,
            symbol=None, symbols=["000001", "600000"], market="zh_a",
        )
        client.security_id_query_params.assert_called_once()
        _, kwargs = client.security_id_query_params.call_args
        assert kwargs["symbols"] == ["000001", "600000"]
        assert kwargs["symbol"] == ""

    def test_security_id_forwarded_directly(self):
        client = self._mock_client()
        self._service()._security_id_params(
            client, security_id=7, security_ids=None,
            symbol=None, symbols=None, market="zh_a",
        )
        client.security_id_query_params.assert_called_once()
        _, kwargs = client.security_id_query_params.call_args
        assert kwargs["security_id"] == 7


class TestGetSnapshotFailFast:
    """Invalid identity must raise BEFORE `_get_runtime` (no phoenixA connection
    attempt for malformed input) — GLM review P2."""

    def test_zero_id_does_not_touch_runtime(self, monkeypatch):
        def _boom(*a, **kw):
            raise AssertionError("_get_runtime must not be called for invalid identity")
        monkeypatch.setattr(factor_service, "_get_runtime", _boom)
        with pytest.raises(ValueError, match="positive"):
            factor_service.get_snapshot(security_id=0, as_of_date="20250101")

    def test_negative_id_does_not_touch_runtime(self, monkeypatch):
        def _boom(*a, **kw):
            raise AssertionError("_get_runtime must not be called for invalid identity")
        monkeypatch.setattr(factor_service, "_get_runtime", _boom)
        with pytest.raises(ValueError, match="positive"):
            factor_service.get_snapshot(security_id=-5, as_of_date="20250101")

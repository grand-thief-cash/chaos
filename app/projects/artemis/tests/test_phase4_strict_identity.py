"""Phase 4 strict-identity tests (refactor §3.6).

Verifies that explicit-but-bad identity (empty / non-positive) raises → 400
at the boundary, never silently degrades to a subset compute or an unfiltered
query. The symbol convenience layer has been removed (no dual-track); identity
is security_id-only.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from artemis.api.http_gateway import _identity


class TestParseSecurityIds:
    def test_absent_returns_none(self):
        assert _identity._parse_security_ids(None) is None

    def test_valid_list(self):
        assert _identity._parse_security_ids("1,2,3") == [1, 2, 3]

    def test_single(self):
        assert _identity._parse_security_ids("42") == [42]

    def test_empty_token_consecutive_comma_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_ids("1,,2")
        assert exc.value.status_code == 400

    def test_present_empty_raises_400(self):
        # ?security_ids= → "" → must NOT become None (would degrade to unfiltered)
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_ids("")
        assert exc.value.status_code == 400

    def test_leading_trailing_comma_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_ids(",1,2,")
        assert exc.value.status_code == 400

    def test_non_numeric_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_ids("1,abc,2")
        assert exc.value.status_code == 400

    def test_zero_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_ids("1,0,2")
        assert exc.value.status_code == 400

    def test_negative_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_ids("-1")
        assert exc.value.status_code == 400


class TestParseSecurityId:
    """Singular security_id query param → 400 (not FastAPI 422) on bad input.

    Mirrors `_parse_security_ids` so both identity shapes return a uniform 400 +
    `{"detail": "..."}` envelope (GLM review P2/P3).
    """

    def test_absent_returns_none(self):
        assert _identity._parse_security_id(None) is None

    def test_valid(self):
        assert _identity._parse_security_id("5") == 5

    def test_whitespace_trimmed(self):
        assert _identity._parse_security_id("  5  ") == 5

    def test_empty_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_id("")
        assert exc.value.status_code == 400

    def test_zero_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_id("0")
        assert exc.value.status_code == 400

    def test_negative_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_id("-1")
        assert exc.value.status_code == 400

    def test_non_numeric_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            _identity._parse_security_id("abc")
        assert exc.value.status_code == 400

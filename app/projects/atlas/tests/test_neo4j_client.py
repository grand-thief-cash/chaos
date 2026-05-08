"""Tests for neo4j_client PhoenixA delegation layer."""
import pytest
from unittest.mock import AsyncMock, patch

from atlas.connectors.neo4j_client import get_session, _PhoenixASession, _ResultProxy


class TestResultProxy:
    def test_data_returns_all_rows(self):
        proxy = _ResultProxy([{"a": 1}, {"a": 2}])
        assert len(proxy.data()) == 2

    def test_single_returns_first(self):
        proxy = _ResultProxy([{"a": 1}, {"a": 2}])
        assert proxy.single()["a"] == 1

    def test_single_returns_none_when_empty(self):
        proxy = _ResultProxy([])
        assert proxy.single() is None

    def test_data_returns_empty_list(self):
        proxy = _ResultProxy([])
        assert proxy.data() == []


class TestGetSession:
    def test_yields_session(self):
        with get_session() as session:
            assert isinstance(session, _PhoenixASession)


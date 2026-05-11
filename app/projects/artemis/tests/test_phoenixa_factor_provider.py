"""Unit and integration tests for PhoenixADataProvider.

Tests factor engine data provider using PhoenixA APIs.
Requires PhoenixA service to be running.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict

import pandas as pd

from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.factor_engine.providers.phoenixa_provider import PhoenixADataProvider


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_phoenixa_client():
    """Mock PhoenixA client for unit tests."""
    client = Mock(spec=PhoenixAClient)
    client.get_securities.return_value = {
        "000001": {"symbol": "000001", "name": "平安银行", "exchange": "SZ"},
        "600000": {"symbol": "600000", "name": "浦发银行", "exchange": "SH"},
    }
    return client


@pytest.fixture
def provider(mock_phoenixa_client):
    """Create PhoenixADataProvider with mock client."""
    return PhoenixADataProvider(mock_phoenixa_client, market="zh_a")


# ============================================================================
# Unit Tests (with mock client)
# ============================================================================

class TestGetActiveSymbols:
    """Test get_active_symbols method."""

    def test_returns_symbol_list(self, provider, mock_phoenixa_client):
        """Should return list of active symbols from PhoenixA."""
        result = provider.get_active_symbols("zh_a", "2025-05-01")

        assert isinstance(result, list)
        assert len(result) == 2
        assert "000001" in result
        assert "600000" in result

        # Verify cache was used on second call
        mock_phoenixa_client.get_securities.assert_called_once()
        result2 = provider.get_active_symbols("zh_a", "2025-05-01")
        mock_phoenixa_client.get_securities.assert_called_once()

    def test_uses_market_parameter(self, provider, mock_phoenixa_client):
        """Should pass market parameter to PhoenixA client."""
        provider.get_active_symbols("zh_a", "2025-05-01")

        call_args = mock_phoenixa_client.get_securities.call_args
        assert call_args[1]["market"] == "zh_a"


class TestGetIndustryMap:
    """Test get_industry_map method."""

    def test_returns_industry_mapping(self, provider, mock_phoenixa_client):
        """Should return symbol -> industry_code mapping."""
        # Mock taxonomy query response
        mock_phoenixa_client.get_taxonomy_by_security.side_effect = [
            [{"source": "sw", "taxonomy": "industry", "category_code": "801010"}],
            [{"source": "sw", "taxonomy": "industry", "category_code": "801020"}],
        ]

        result = provider.get_industry_map("sw_l1", "zh_a")

        assert isinstance(result, dict)
        assert result.get("000001") == "801010"
        assert result.get("600000") == "801020"

    def test_filters_by_source(self, provider, mock_phoenixa_client):
        """Should filter mappings by source."""
        # Mock taxonomy query with multiple sources
        mock_phoenixa_client.get_taxonomy_by_security.side_effect = [
            [
                {"source": "sw", "taxonomy": "industry", "category_code": "801010"},
                {"source": "citics", "taxonomy": "industry", "category_code": "C10001"},
            ],
            [
                {"source": "sw", "taxonomy": "industry", "category_code": "801020"},
            ],
        ]

        result = provider.get_industry_map("sw_l1", "zh_a")

        # Should only use sw mappings
        assert result.get("000001") == "801010"
        assert result.get("600000") == "801020"

    def test_uses_cache(self, provider, mock_phoenixa_client):
        """Should cache industry map for repeated calls."""
        mock_phoenixa_client.get_taxonomy_by_security.side_effect = [
            [{"source": "sw", "taxonomy": "industry", "category_code": "801010"}],
            [{"source": "sw", "taxonomy": "industry", "category_code": "801020"}],
        ]

        provider.get_industry_map("sw_l1", "zh_a")
        provider.get_industry_map("sw_l1", "zh_a")

        # Should only call once (cached on second call)
        total_calls = sum(
            call_args[1]["symbol"] == "000001"
            for call_args in mock_phoenixa_client.get_taxonomy_by_security.call_args_list
        )
        assert total_calls == 1

    def test_handles_different_taxonomies(self, provider, mock_phoenixa_client):
        """Should support different taxonomy systems (extensibility)."""
        mock_phoenixa_client.get_taxonomy_by_security.return_value = [
            {"source": "citics", "taxonomy": "industry", "category_code": "C10001"},
        ]

        result = provider.get_industry_map("citics_l1", "zh_a")

        # Should query with citics source
        mock_phoenixa_client.get_taxonomy_by_security.assert_called_once()
        assert isinstance(result, dict)


class TestGetFinancialData:
    """Test get_financial_data method."""

    def test_returns_statement_data(self, provider, mock_phoenixa_client):
        """Should return dict mapping statement_type -> DataFrame."""
        # Mock financial statement response
        mock_response = {
            "data": [
                {
                    "reporting_period": "2024-12-31",
                    "ann_date": "2025-03-21",
                    "data_json": {
                        "TOTAL_ASSETS": 5431234567.89,
                        "TOT_SHARE_EQUITY_EXCL_MIN_INT": 234567890.12,
                        "TOT_SHARE": 19406000000,
                    },
                }
            ],
            "total": 1,
        }
        mock_phoenixa_client.query_financial_statements.return_value = mock_response

        result = provider.get_financial_data("000001", "2025-04-01")

        assert isinstance(result, dict)
        assert "balance_sheet" in result
        assert isinstance(result["balance_sheet"], pd.DataFrame)

    def test_applies_pit_filter(self, provider, mock_phoenixa_client):
        """Should apply PIT (ann_date_before) filtering."""
        provider.get_financial_data("000001", "2025-04-01")

        call_args = mock_phoenixa_client.query_financial_statements.call_args
        assert call_args[1]["ann_date_before"] == "2025-04-01"

    def test_expands_data_json(self, provider, mock_phoenixa_client):
        """Should expand data_json fields into DataFrame columns."""
        mock_response = {
            "data": [
                {
                    "reporting_period": "2024-12-31",
                    "data_json": {
                        "TOTAL_ASSETS": 5431234567.89,
                        "CURRENCY_CAP": 123456789.01,
                    },
                },
            ],
            "total": 1,
        }
        mock_phoenixa_client.query_financial_statements.return_value = mock_response

        result = provider.get_financial_data("000001", "2025-04-01")
        df = result["balance_sheet"]

        # data_json fields should be expanded as columns
        assert "TOTAL_ASSETS" in df.columns
        assert "CURRENCY_CAP" in df.columns
        assert df["TOTAL_ASSETS"].iloc[0] == 5431234567.89

    def test_sorts_by_period_desc(self, provider, mock_phoenixa_client):
        """Should sort DataFrame by reporting_period descending (newest first)."""
        mock_response = {
            "data": [
                {
                    "reporting_period": "2024-09-30",
                    "data_json": {"TOTAL_ASSETS": 5.0e9},
                },
                {
                    "reporting_period": "2024-12-31",
                    "data_json": {"TOTAL_ASSETS": 5.5e9},
                },
            ],
            "total": 2,
        }
        mock_phoenixa_client.query_financial_statements.return_value = mock_response

        result = provider.get_financial_data("000001", "2025-04-01")
        df = result["balance_sheet"]

        # Should be sorted with newest first
        periods = list(df.index)
        assert periods[0] == "2024-12-31"
        assert periods[1] == "2024-09-30"


class TestGetMarketData:
    """Test get_market_data method."""

    def test_returns_bars_dataframe(self, provider, mock_phoenixa_client):
        """Should return DataFrame with OHLCV data."""
        mock_bars = [
            {
                "trade_date": "2025-04-01",
                "open": 12.34,
                "high": 12.56,
                "low": 12.28,
                "close": 12.45,
                "volume": 12345678,
            }
        ]
        mock_phoenixa_client.get_bars.return_value = mock_bars

        result = provider.get_market_data("000001", "2025-04-01")

        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert result.index.name == "trade_date"
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns

    def test_passes_correct_params(self, provider, mock_phoenixa_client):
        """Should pass correct parameters to PhoenixA client."""
        provider.get_market_data("000001", "2025-04-01")

        call_args = mock_phoenixa_client.get_bars.call_args
        assert call_args[1]["symbol"] == "000001"
        assert call_args[1]["start_date"] == "2025-04-01"
        assert call_args[1]["end_date"] == "2025-04-01"
        assert call_args[1]["asset_type"] == "stock"
        assert call_args[1]["market"] == "zh_a"
        assert call_args[1]["period"] == "daily"
        assert call_args[1]["adjust"] == "nf"

    def test_returns_none_on_empty_response(self, provider, mock_phoenixa_client):
        """Should return None when no bars data."""
        mock_phoenixa_client.get_bars.return_value = []

        result = provider.get_market_data("000001", "2025-04-01")

        assert result is None


class TestGetCurrentPeriod:
    """Test get_current_period method."""

    def test_returns_latest_period(self, provider, mock_phoenixa_client):
        """Should return the latest reporting period."""
        mock_response = {
            "data": [
                {
                    "reporting_period": "2024-12-31",
                    "ann_date": "2025-03-21",
                },
                {
                    "reporting_period": "2024-09-30",
                    "ann_date": "2024-10-28",
                },
            ],
            "total": 2,
        }
        mock_phoenixa_client.query_financial_statements.return_value = mock_response

        result = provider.get_current_period("000001", "2025-04-01")

        assert result == "2024-12-31"

    def test_applies_pit_filter(self, provider, mock_phoenixa_client):
        """Should apply PIT (ann_date_before) filtering."""
        provider.get_current_period("000001", "2025-04-01")

        call_args = mock_phoenixa_client.query_financial_statements.call_args
        assert call_args[1]["ann_date_before"] == "2025-04-01"

    def test_returns_none_on_empty_response(self, provider, mock_phoenixa_client):
        """Should return None when no data."""
        mock_phoenixa_client.query_financial_statements.return_value = {"data": [], "total": 0}

        result = provider.get_current_period("000001", "2025-04-01")

        assert result is None


class TestCacheManagement:
    """Test caching behavior."""

    def test_clear_cache(self, provider, mock_phoenixa_client):
        """clear_cache should clear all cached data."""
        # Populate cache
        provider.get_active_symbols("zh_a", "2025-04-01")
        provider.get_industry_map("sw_l1", "zh_a")

        # Clear cache
        provider.clear_cache()

        # Should make fresh calls next time
        provider.get_active_symbols("zh_a", "2025-04-01")
        assert mock_phoenixa_client.get_securities.call_count == 2

        provider.get_industry_map("sw_l1", "zh_a")
        # Each symbol would be queried again
        assert mock_phoenixa_client.get_taxonomy_by_security.call_count > 2


# ============================================================================
# Conversion Helpers Tests
# ============================================================================

class TestConvertFinancialResponse:
    """Test _convert_financial_response static method."""

    def test_converts_to_dataframe(self):
        """Should convert API response to DataFrame."""
        data = [
            {
                "reporting_period": "2024-12-31",
                "ann_date": "2025-03-21",
                "data_json": {
                    "TOTAL_ASSETS": 5.5e9,
                    "EQUITY": 2.0e9,
                },
            },
        ]

        result = PhoenixADataProvider._convert_financial_response(data)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.index.name == "reporting_period"
        assert "TOTAL_ASSETS" in result.columns
        assert "EQUITY" in result.columns

    def test_handles_empty_data(self):
        """Should return empty DataFrame for empty data."""
        result = PhoenixADataProvider._convert_financial_response([])

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_merges_data_json_fields(self):
        """Should merge data_json fields into DataFrame columns."""
        data = [
            {
                "reporting_period": "2024-12-31",
                "data_json": {"A": 1, "B": 2},
            },
        ]

        result = PhoenixADataProvider._convert_financial_response(data)

        assert "A" in result.columns
        assert "B" in result.columns
        assert "data_json" not in result.columns  # data_json should be expanded, not kept

    def test_sorts_descending(self):
        """Should sort by reporting_period descending."""
        data = [
            {"reporting_period": "2024-09-30", "data_json": {"X": 1}},
            {"reporting_period": "2024-12-31", "data_json": {"X": 2}},
            {"reporting_period": "2024-06-30", "data_json": {"X": 3}},
        ]

        result = PhoenixADataProvider._convert_financial_response(data)

        periods = list(result.index)
        assert periods[0] == "2024-12-31"
        assert periods[1] == "2024-09-30"
        assert periods[2] == "2024-06-30"

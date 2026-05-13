"""PhoenixA data provider for factor engine.

Implements FactorDataProvider protocol using PhoenixA HTTP APIs.
See docs/2026-05-11 FACTOR_ENGINE_DATA_CONTRACT.md for contract details.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.log.logger import get_logger

logger = get_logger("phoenixa_factor_provider")

# AmazingData source name
SOURCE = "amazing_data"


class PhoenixADataProvider:
    """FactorDataProvider implementation using PhoenixA APIs.

    Provides financial data, market data, securities, and taxonomy
    for factor engine calculations.
    """

    def __init__(self, client: PhoenixAClient, market: str = "zh_a"):
        """Initialize provider with PhoenixA client.

        Args:
            client: PhoenixAClient instance
            market: Market code (default: zh_a)
        """
        self.client = client
        self.market = market
        self._cache: Dict[tuple, any] = {}

    def get_active_symbols(self, market: str, as_of_date: str) -> List[str]:
        """Get list of active symbols for a market.

        Args:
            market: Market code (e.g., "zh_a")
            as_of_date: Reference date (not used currently)

        Returns:
            List of active symbol codes (e.g., ["000001", "600000"])
        """
        cache_key = ("active_symbols", market, as_of_date)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            securities = self.client.get_securities(
                asset_type="stock",
                market=market,
                limit=10000,
            )
            symbols = list(securities.keys())
            self._cache[cache_key] = symbols
            logger.info({
                "event": "phoenixa_get_active_symbols",
                "market": market,
                "count": len(symbols),
            })
            return symbols
        except Exception as e:
            logger.error({
                "event": "phoenixa_get_active_symbols_failed",
                "market": market,
                "error": str(e),
            })
            return []

    def get_industry_map(self, taxonomy: str, market: str) -> Dict[str, str]:
        """Get industry classification mapping for all symbols.

        Supports multiple taxonomy systems (extensible):
          - "sw_l1" or "sw": Shenwan Level-1 (申万一级行业)
          - "sw_l2": Shenwan Level-2 (申万二级行业)
          - "sw_l3": Shenwan Level-3 (申万三级行业)
          - Future: "citics", "wind", etc. (as added to PhoenixA)

        Args:
            taxonomy: Taxonomy name (e.g., "sw_l1" for Shenwan L1)
            market: Market code

        Returns:
            Dict mapping symbol -> industry_code
        """
        cache_key = ("industry_map", taxonomy, market)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Get all active symbols first
            symbols = self.get_active_symbols(market, "")

            # Build industry map by querying each symbol
            industry_map: Dict[str, str] = {}
            # Extract source from taxonomy name (e.g., "sw_l1" -> "sw")
            source = "sw" if "sw" in taxonomy.lower() else taxonomy

            for symbol in symbols:
                try:
                    mappings = self.client.get_taxonomy_by_security(symbol)
                    for m in mappings:
                        if m.get("source") == source and m.get("taxonomy") == "industry":
                            industry_map[symbol] = m.get("category_code", "")
                            break
                except Exception as e:
                    logger.warning({
                        "event": "phoenixa_get_industry_failed",
                        "symbol": symbol,
                        "error": str(e),
                    })

            self._cache[cache_key] = industry_map
            logger.info({
                "event": "phoenixa_get_industry_map",
                "taxonomy": taxonomy,
                "market": market,
                "mapped_count": len(industry_map),
            })
            return industry_map
        except Exception as e:
            logger.error({
                "event": "phoenixa_get_industry_map_failed",
                "taxonomy": taxonomy,
                "market": market,
                "error": str(e),
            })
            return {}

    def get_financial_data(
        self, symbol: str, as_of_date: str,
    ) -> Dict[str, pd.DataFrame]:
        """Get financial data for a symbol with PIT filtering.

        Returns data for 3 statement types: balance_sheet, income, cashflow.

        Args:
            symbol: Stock symbol (e.g., "000001")
            as_of_date: Reference date for PIT filtering

        Returns:
            Dict mapping statement_type -> DataFrame with reporting_period as index
        """
        cache_key = ("financial_data", symbol, as_of_date)
        if cache_key in self._cache:
            return self._cache[cache_key]

        result: Dict[str, pd.DataFrame] = {}

        # Query each statement type
        statement_types = ["balance_sheet", "income", "cashflow"]
        for stmt_type in statement_types:
            try:
                response = self.client.query_financial_statements(
                    source=SOURCE,
                    statement_type=stmt_type,
                    symbol=symbol,
                    ann_date_before=as_of_date,  # PIT filtering
                    page_size=20,  # Get recent periods
                )

                if response.get("data"):
                    df = self._convert_financial_response(response["data"])
                    result[stmt_type] = df
                    logger.debug({
                        "event": "phoenixa_get_financial_data",
                        "symbol": symbol,
                        "stmt_type": stmt_type,
                        "periods_count": len(df),
                    })
            except Exception as e:
                logger.warning({
                    "event": "phoenixa_get_financial_data_failed",
                    "symbol": symbol,
                    "stmt_type": stmt_type,
                    "error": str(e),
                })

        self._cache[cache_key] = result
        return result

    def get_market_data(self, symbol: str, as_of_date: str) -> Optional[pd.DataFrame]:
        """Get market data (OHLCV) for a symbol.

        Args:
            symbol: Stock symbol
            as_of_date: Reference date

        Returns:
            DataFrame with trade_date as index, columns: open, high, low, close, volume
        """
        cache_key = ("market_data", symbol, as_of_date)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            bars = self.client.get_bars(
                asset_type="stock",
                market=self.market,
                symbol=symbol,
                start_date=as_of_date,
                end_date=as_of_date,
                period="daily",
                adjust="nf",  # No adjustment
            )

            if bars:
                df = pd.DataFrame(bars)
                df.set_index("trade_date", inplace=True)
                # Select required columns
                df = df[["open", "high", "low", "close", "volume"]]
                self._cache[cache_key] = df
                return df
        except Exception as e:
            logger.warning({
                "event": "phoenixa_get_market_data_failed",
                "symbol": symbol,
                "as_of_date": as_of_date,
                "error": str(e),
            })

        return None

    def get_current_period(self, symbol: str, as_of_date: str) -> Optional[str]:
        """Get the latest reporting period available as of a date.

        Args:
            symbol: Stock symbol
            as_of_date: Reference date for PIT filtering

        Returns:
            Latest reporting_period string (e.g., "2024-12-31") or None
        """
        cache_key = ("current_period", symbol, as_of_date)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Query balance sheet with PIT filtering, get latest period
            response = self.client.query_financial_statements(
                source=SOURCE,
                statement_type="balance_sheet",
                symbol=symbol,
                ann_date_before=as_of_date,
                page_size=1,
            )

            if response.get("data"):
                # Data is sorted by reporting_period DESC
                latest_period = response["data"][0].get("reporting_period")
                self._cache[cache_key] = latest_period
                return latest_period
        except Exception as e:
            logger.warning({
                "event": "phoenixa_get_current_period_failed",
                "symbol": symbol,
                "as_of_date": as_of_date,
                "error": str(e),
            })

        return None

    def clear_cache(self):
        """Clear internal cache."""
        self._cache.clear()

    @staticmethod
    def _convert_financial_response(data: List[Dict]) -> pd.DataFrame:
        """Convert PhoenixA financial statement response to DataFrame.

        Args:
            data: List of FinancialStatement records from PhoenixA

        Returns:
            DataFrame with reporting_period as index, columns from data_json
        """
        if not data:
            return pd.DataFrame()

        rows = []
        for item in data:
            row = {
                "reporting_period": item.get("reporting_period"),
                "ann_date": item.get("ann_date"),
            }
            # Merge data_json fields
            data_json = item.get("data_json") or {}
            row.update(data_json)
            rows.append(row)

        df = pd.DataFrame(rows)
        if not df.empty:
            df.set_index("reporting_period", inplace=True)
            # Sort by period descending (newest first)
            df.sort_index(ascending=False, inplace=True)

        return df

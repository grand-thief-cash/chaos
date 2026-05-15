"""PhoenixA data provider for factor engine.

Implements FactorDataProvider protocol using PhoenixA HTTP APIs.
See docs/2026-05-11 FACTOR_ENGINE_DATA_CONTRACT.md for contract details.
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from artemis.consts.task_params import ADJUST_NONE
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.factor_engine.ttm import normalize_date, normalize_period
from artemis.log.logger import get_logger

logger = get_logger("phoenixa_factor_provider")

# AmazingData source name
SOURCE = "amazing_data"

# Concurrent settings
MAX_WORKERS = 10
BATCH_SIZE = 50


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""
    value: Any
    timestamp: float
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.timestamp > self.ttl_seconds


class PhoenixADataProvider:
    """FactorDataProvider implementation using PhoenixA APIs.

    Provides financial data, market data, securities, and taxonomy
    for factor engine calculations.

    Cache TTL configuration (in seconds):
    - active_symbols: 3600 (1 hour)
    - industry_map: 86400 (24 hours)
    - financial_data: 3600 (1 hour)
    - market_data: 300 (5 minutes)
    - current_period: 3600 (1 hour)
    - dividend_per_share: 86400 (24 hours)
    """

    # Cache TTL settings (in seconds)
    TTL_ACTIVE_SYMBOLS = 3600
    TTL_INDUSTRY_MAP = 86400
    TTL_FINANCIAL_DATA = 3600
    TTL_MARKET_DATA = 300
    TTL_CURRENT_PERIOD = 3600
    TTL_DIVIDEND_PER_SHARE = 86400

    def __init__(self, client: PhoenixAClient, market: str = "zh_a", market_adjust: str = ADJUST_NONE):
        """Initialize provider with PhoenixA client.

        Args:
            client: PhoenixAClient instance
            market: Market code (default: zh_a)
            market_adjust: Bars adjust mode for factor-engine market data
        """
        self.client = client
        self.market = market
        self.market_adjust = market_adjust
        self._cache: Dict[tuple, CacheEntry] = {}

    def get_active_symbols(self, market: str, as_of_date: str) -> List[str]:
        """Get list of active symbols for a market.

        Args:
            market: Market code (e.g., "zh_a")
            as_of_date: Reference date (not used currently)

        Returns:
            List of active symbol codes (e.g., ["000001", "600000"])
        """
        cache_key = ("active_symbols", market, as_of_date)
        entry = self._cache.get(cache_key)
        if entry is not None:
            if entry.is_expired():
                del self._cache[cache_key]
                logger.info({"event": "cache_expired", "key": cache_key})
            else:
                return entry.value

        try:
            securities = self.client.get_securities(
                asset_type="stock",
                market=market,
                limit=10000,
            )
            normalized_as_of = normalize_date(as_of_date)
            symbols = [
                symbol
                for symbol, info in securities.items()
                if self._security_active_as_of(info, normalized_as_of)
            ]
            self._cache[cache_key] = CacheEntry(
                value=symbols,
                timestamp=time.time(),
                ttl_seconds=self.TTL_ACTIVE_SYMBOLS,
            )
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

    def get_industry_map(
        self,
        taxonomy: str,
        market: str,
        use_batch: bool = True,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Get industry classification mapping for symbols.

        Supports multiple taxonomy systems (extensible):
          - "sw_l1" or "sw": Shenwan Level-1 (申万一级行业)
          - "sw_l2": Shenwan Level-2 (申万二级行业)
          - "sw_l3": Shenwan Level-3 (申万三级行业)
          - Future: "citics", "wind", etc. (as added to PhoenixA)

        Args:
            taxonomy: Taxonomy name (e.g., "sw_l1" for Shenwan L1)
            market: Market code
            use_batch: Whether to use batch concurrent queries (default True)
            symbols: Optional list of symbols to query. If None, fetch all active symbols.

        Returns:
            Dict mapping symbol -> industry_code
        """
        full_map_entry = self._cache.get(self._industry_map_cache_key(taxonomy, market))
        if full_map_entry is not None:
            if full_map_entry.is_expired():
                self._drop_industry_full_cache(taxonomy, market)
            else:
                if symbols is None:
                    return full_map_entry.value
                return {k: v for k, v in full_map_entry.value.items() if k in symbols}

        if symbols is not None:
            cached_subset = self._get_cached_industry_subset(taxonomy, market, symbols)
            if cached_subset is not None:
                return cached_subset

        try:
            if use_batch:
                return self.get_industry_map_batch(taxonomy, market, symbols)
            else:
                is_full_request = symbols is None
                symbols = symbols or self._get_active_symbols_for_market(market)

                # Build industry map by querying each symbol (legacy, slower)
                industry_map: Dict[str, str] = {}
                industry_context_map: Dict[str, Dict[str, Any]] = {}
                taxonomy_lower = taxonomy.lower()

                for symbol in symbols:
                    try:
                        mappings = self.client.get_taxonomy_by_security(symbol)
                        for m in mappings:
                            industry_context = self._match_industry_mapping(m, taxonomy_lower)
                            industry_code = industry_context.get("industry_code", "")
                            if industry_code:
                                industry_map[symbol] = industry_code
                                industry_context_map[symbol] = industry_context
                                break
                    except Exception as e:
                        logger.warning({
                            "event": "phoenixa_get_industry_failed",
                            "symbol": symbol,
                            "error": str(e),
                        })

                self._cache_industry_results(
                    taxonomy,
                    market,
                    industry_map,
                    industry_context_map,
                    complete=is_full_request,
                )
                logger.info({
                    "event": "phoenixa_get_industry_map",
                    "taxonomy": taxonomy,
                    "market": market,
                    "mapped_count": len(industry_map),
                    "use_batch": False,
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
        entry = self._cache.get(cache_key)
        if entry is not None:
            if entry.is_expired():
                del self._cache[cache_key]
                logger.info({"event": "cache_expired", "key": cache_key})
            else:
                return entry.value

        result: Dict[str, pd.DataFrame] = {}
        api_as_of_date = self._to_api_date(as_of_date)

        # Query each statement type
        statement_types = ["balance_sheet", "income", "cashflow"]
        for stmt_type in statement_types:
            try:
                response = self.client.query_financial_statements(
                    source=SOURCE,
                    statement_type=stmt_type,
                    symbol=symbol,
                    ann_date_before=api_as_of_date,  # PIT filtering
                    page_size=24,  # Get enough periods for TTM/CAGR
                )

                if isinstance(response, dict) and response.get("data"):
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

        self._cache[cache_key] = CacheEntry(
            value=result,
            timestamp=time.time(),
            ttl_seconds=self.TTL_FINANCIAL_DATA,
        )
        return result

    def get_market_data(self, symbol: str, as_of_date: str, adjust: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Get market data (OHLCV) for a symbol.

        Args:
            symbol: Stock symbol
            as_of_date: Reference date

        Returns:
            DataFrame with trade_date as index, columns: open, high, low, close, volume
        """
        resolved_adjust = adjust or self.market_adjust
        cache_key = ("market_data", symbol, as_of_date, resolved_adjust)
        entry = self._cache.get(cache_key)
        if entry is not None:
            if entry.is_expired():
                del self._cache[cache_key]
                logger.info({"event": "cache_expired", "key": cache_key})
            else:
                return entry.value

        try:
            bars = self.client.get_bars(
                asset_type="stock",
                market=self.market,
                symbol=symbol,
                start_date=self._to_api_date(as_of_date),
                end_date=self._to_api_date(as_of_date),
                period="daily",
                adjust=resolved_adjust,
                fields=["trade_date", "symbol", "open", "high", "low", "close", "volume", "amount"],
                normalize_for_cache=False,
            )

            if bars:
                df = pd.DataFrame(bars)
                if "trade_date" in df.columns:
                    df["trade_date"] = df["trade_date"].map(normalize_date)
                df.set_index("trade_date", inplace=True)
                # Select required columns
                keep_cols = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df.columns]
                df = df[keep_cols]
                df["adjust"] = resolved_adjust

                total_share = self._get_latest_balance_value(symbol, as_of_date, "TOT_SHARE")
                if total_share is not None:
                    df["total_share"] = float(total_share)
                    if "close" in df.columns:
                        df["market_cap"] = df["close"].astype(float) * float(total_share)

                dps = self._get_latest_dividend_per_share(symbol, as_of_date)
                if dps is not None:
                    df["dps"] = float(dps)

                self._cache[cache_key] = CacheEntry(
                    value=df,
                    timestamp=time.time(),
                    ttl_seconds=self.TTL_MARKET_DATA,
                )
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
        entry = self._cache.get(cache_key)
        if entry is not None:
            if entry.is_expired():
                del self._cache[cache_key]
                logger.info({"event": "cache_expired", "key": cache_key})
            else:
                return entry.value

        try:
            # Query balance sheet with PIT filtering, get latest period
            response = self.client.query_financial_statements(
                source=SOURCE,
                statement_type="balance_sheet",
                symbol=symbol,
                ann_date_before=self._to_api_date(as_of_date),
                page_size=1,
            )

            if isinstance(response, dict) and response.get("data"):
                # Data is sorted by reporting_period DESC
                latest_period = normalize_period(
                    response["data"][0].get("reporting_period") or response["data"][0].get("report_period"),
                )
                self._cache[cache_key] = CacheEntry(
                    value=latest_period,
                    timestamp=time.time(),
                    ttl_seconds=self.TTL_CURRENT_PERIOD,
                )
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

    def get_industry_context(self, symbol: str, taxonomy: str, market: str) -> Dict[str, Any]:
        symbol_key = self._industry_symbol_context_cache_key(taxonomy, market, symbol)
        entry = self._cache.get(symbol_key)
        if entry is not None:
            if entry.is_expired():
                del self._cache[symbol_key]
            else:
                return dict(entry.value or {})

        context_map_entry = self._cache.get(self._industry_context_map_cache_key(taxonomy, market))
        if context_map_entry is not None:
            if context_map_entry.is_expired():
                self._drop_industry_full_cache(taxonomy, market)
            else:
                value = (context_map_entry.value or {}).get(symbol) or {}
                if value:
                    self._cache[symbol_key] = CacheEntry(
                        value=dict(value),
                        timestamp=time.time(),
                        ttl_seconds=self.TTL_INDUSTRY_MAP,
                    )
                return dict(value)

        self.get_industry_map(taxonomy, market, symbols=[symbol])
        entry = self._cache.get(symbol_key)
        return dict(entry.value or {}) if entry and not entry.is_expired() else {}

    def _get_active_symbols_for_market(self, market: str) -> List[str]:
        for key, entry in self._cache.items():
            if len(key) == 3 and key[0] == "active_symbols" and key[1] == market:
                if entry.is_expired():
                    del self._cache[key]
                else:
                    return entry.value
        return self.get_active_symbols(market, "")

    def _get_latest_balance_value(self, symbol: str, as_of_date: str, field: str) -> Optional[float]:
        fin = self.get_financial_data(symbol, as_of_date)
        balance = fin.get("balance_sheet")
        if balance is None or balance.empty or field not in balance.columns:
            return None
        series = balance[field].dropna()
        if series.empty:
            return None
        return float(series.iloc[0])

    def _get_latest_dividend_per_share(self, symbol: str, as_of_date: str) -> Optional[float]:
        cache_key = ("dividend_per_share", symbol, as_of_date)
        entry = self._cache.get(cache_key)
        if entry is not None:
            if entry.is_expired():
                del self._cache[cache_key]
                logger.info({"event": "cache_expired", "key": cache_key})
            else:
                return entry.value

        api_as_of_date = self._to_api_date(as_of_date)
        queries = [
            {"progress_code": "3"},
            {},
        ]
        for extra in queries:
            response = self.client.query_corporate_actions(
                source=SOURCE,
                action_type="dividend",
                symbol=symbol,
                ann_date_before=api_as_of_date,
                page_size=20,
                **extra,
            )
            if not isinstance(response, dict):
                continue
            for item in response.get("data", []):
                data_json = item.get("data_json") or {}
                value = data_json.get("DVD_PER_SHARE_PRE_TAX_CASH")
                if value is not None:
                    self._cache[cache_key] = CacheEntry(
                        value=float(value),
                        timestamp=time.time(),
                        ttl_seconds=self.TTL_DIVIDEND_PER_SHARE,
                    )
                    return float(value)

        self._cache[cache_key] = CacheEntry(
            value=None,
            timestamp=time.time(),
            ttl_seconds=self.TTL_DIVIDEND_PER_SHARE,
        )
        return None

    @staticmethod
    def _to_api_date(value: str) -> str:
        normalized = normalize_date(value)
        if len(normalized) == 8:
            return f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}"
        return value

    @staticmethod
    def _security_active_as_of(info: Dict[str, Any], as_of_date: str) -> bool:
        if not as_of_date:
            return True
        list_date = normalize_date(info.get("list_date"))
        delist_date = normalize_date(info.get("delist_date"))
        if list_date and list_date > as_of_date:
            return False
        if delist_date and delist_date < as_of_date:
            return False
        return True

    @staticmethod
    def _industry_map_cache_key(taxonomy: str, market: str) -> tuple:
        return ("industry_map", taxonomy, market, "__all__")

    @staticmethod
    def _industry_context_map_cache_key(taxonomy: str, market: str) -> tuple:
        return ("industry_context_map", taxonomy, market, "__all__")

    @staticmethod
    def _industry_symbol_context_cache_key(taxonomy: str, market: str, symbol: str) -> tuple:
        return ("industry_context", taxonomy, market, symbol)

    def _drop_industry_full_cache(self, taxonomy: str, market: str) -> None:
        for key in [
            self._industry_map_cache_key(taxonomy, market),
            self._industry_context_map_cache_key(taxonomy, market),
        ]:
            if key in self._cache:
                del self._cache[key]

    def _get_cached_industry_subset(
        self,
        taxonomy: str,
        market: str,
        symbols: Iterable[str],
    ) -> Optional[Dict[str, str]]:
        subset, _, missing_symbols = self._split_cached_industry_subset(taxonomy, market, symbols)
        if missing_symbols:
            return None
        return subset

    def _split_cached_industry_subset(
        self,
        taxonomy: str,
        market: str,
        symbols: Iterable[str],
    ) -> tuple[Dict[str, str], Dict[str, Dict[str, Any]], List[str]]:
        subset: Dict[str, str] = {}
        context_map: Dict[str, Dict[str, Any]] = {}
        missing_symbols: List[str] = []
        for symbol in symbols:
            cache_key = self._industry_symbol_context_cache_key(taxonomy, market, symbol)
            ctx_entry = self._cache.get(cache_key)
            if ctx_entry is None:
                missing_symbols.append(symbol)
                continue
            if ctx_entry.is_expired():
                del self._cache[cache_key]
                missing_symbols.append(symbol)
                continue
            context = dict(ctx_entry.value or {})
            industry_code = str(context.get("industry_code") or "")
            if industry_code:
                subset[symbol] = industry_code
            context_map[symbol] = context
        return subset, context_map, missing_symbols

    def _cache_industry_results(
        self,
        taxonomy: str,
        market: str,
        industry_map: Dict[str, str],
        industry_context_map: Dict[str, Dict[str, Any]],
        *,
        complete: bool,
    ) -> None:
        timestamp = time.time()
        for symbol, context in industry_context_map.items():
            self._cache[self._industry_symbol_context_cache_key(taxonomy, market, symbol)] = CacheEntry(
                value=dict(context),
                timestamp=timestamp,
                ttl_seconds=self.TTL_INDUSTRY_MAP,
            )
        if complete:
            self._cache[self._industry_map_cache_key(taxonomy, market)] = CacheEntry(
                value=dict(industry_map),
                timestamp=timestamp,
                ttl_seconds=self.TTL_INDUSTRY_MAP,
            )
            self._cache[self._industry_context_map_cache_key(taxonomy, market)] = CacheEntry(
                value={symbol: dict(context) for symbol, context in industry_context_map.items()},
                timestamp=timestamp,
                ttl_seconds=self.TTL_INDUSTRY_MAP,
            )

    @staticmethod
    def _match_industry_mapping(mapping: Dict, taxonomy_lower: str) -> Dict[str, Any]:
        def _lower(value) -> str:
            return str(value or "").strip().lower()

        def _text(value) -> str:
            return str(value or "").strip()

        industry_code = _text(mapping.get("canonical_category_code"))
        if not industry_code:
            return {}

        canonical_taxonomy = _lower(mapping.get("canonical_taxonomy"))
        canonical_source = _lower(mapping.get("canonical_source"))
        canonical_level = _text(mapping.get("canonical_level"))
        expected_source, expected_level = PhoenixADataProvider._expected_taxonomy_target(taxonomy_lower)
        if not expected_source:
            return {}
        if canonical_source != expected_source or canonical_taxonomy != expected_source:
            return {}
        if expected_level and canonical_level != expected_level:
            return {}

        flags = mapping.get("derived_flags") or {}
        if not isinstance(flags, dict):
            flags = {}

        return {
            "industry_code": industry_code,
            "canonical_source": canonical_source,
            "canonical_taxonomy": canonical_taxonomy,
            "canonical_level": canonical_level,
            "canonical_index_code": _text(mapping.get("canonical_index_code")),
            "derived_flags": {str(k): bool(v) for k, v in flags.items()},
        }

    @staticmethod
    def _expected_taxonomy_target(taxonomy_lower: str) -> tuple[str, str]:
        normalized = str(taxonomy_lower or "").strip().lower()
        if normalized.startswith("sw"):
            return "sw", PhoenixADataProvider._extract_taxonomy_level(normalized)
        if normalized.startswith("citics"):
            return "citics", PhoenixADataProvider._extract_taxonomy_level(normalized)
        return normalized, ""

    @staticmethod
    def _extract_taxonomy_level(taxonomy_lower: str) -> str:
        normalized = str(taxonomy_lower or "").strip().lower()
        if "_l" in normalized:
            return normalized.rsplit("_l", 1)[-1]
        return "1" if normalized in {"sw", "citics"} else ""

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
                "reporting_period": normalize_period(item.get("reporting_period") or item.get("report_period")),
                "ann_date": normalize_date(item.get("ann_date")),
                "comp_type_code": item.get("comp_type_code"),
            }
            # Merge data_json fields
            data_json = item.get("data_json") or {}
            row.update(data_json)
            rows.append(row)

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df[df["reporting_period"] != ""].copy()
            df.sort_values(["reporting_period", "ann_date"], ascending=[False, False], inplace=True)
            df.set_index("reporting_period", drop=False, inplace=True)

        return df

    # ────────────────────────────────────────────────────────────────────
    # Batch query methods for performance optimization
    # ────────────────────────────────────────────────────────────────────

    def get_industry_map_batch(
        self,
        taxonomy: str,
        market: str,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Batch query industry classification for symbols.

        This method uses concurrent requests for better performance when
        querying many symbols. For small batches (< 50 symbols),
        the performance gain may be negligible compared to the overhead.

        Args:
            taxonomy: Taxonomy name (e.g., "sw_l1" for Shenwan L1)
            market: Market code
            symbols: Optional list of symbols. If None, fetch all active symbols.

        Returns:
            Dict mapping symbol -> industry_code
        """
        full_map_key = self._industry_map_cache_key(taxonomy, market)
        entry = self._cache.get(full_map_key)
        if entry is not None:
            if entry.is_expired():
                self._drop_industry_full_cache(taxonomy, market)
                logger.info({"event": "cache_expired", "key": full_map_key})
            else:
                if symbols is None:
                    return entry.value
                return {k: v for k, v in entry.value.items() if k in symbols}

        full_request = symbols is None
        requested_symbols = list(symbols or self._get_active_symbols_for_market(market))

        taxonomy_lower = taxonomy.lower()
        industry_map, industry_context_map, missing_symbols = self._split_cached_industry_subset(
            taxonomy,
            market,
            requested_symbols,
        )

        # Use ThreadPoolExecutor for concurrent queries
        def fetch_industry_for_symbol(symbol: str) -> tuple:
            try:
                mappings = self.client.get_taxonomy_by_security(symbol)
                for m in mappings:
                    industry_context = self._match_industry_mapping(m, taxonomy_lower)
                    industry_code = industry_context.get("industry_code", "")
                    if industry_code:
                        return symbol, industry_code, industry_context
                return symbol, "", {}
            except Exception as e:
                logger.warning({
                    "event": "phoenixa_get_industry_failed",
                    "symbol": symbol,
                    "error": str(e),
                })
                return symbol, "", {}

        # Process symbols in batches
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for i in range(0, len(missing_symbols), BATCH_SIZE):
                batch = missing_symbols[i:i + BATCH_SIZE]
                futures = [executor.submit(fetch_industry_for_symbol, sym) for sym in batch]
                for future in concurrent.futures.as_completed(futures):
                    symbol, industry_code, industry_context = future.result()
                    if industry_code:
                        industry_map[symbol] = industry_code
                        industry_context_map[symbol] = industry_context

        self._cache_industry_results(
            taxonomy,
            market,
            industry_map,
            industry_context_map,
            complete=full_request,
        )

        logger.info({
            "event": "phoenixa_get_industry_map_batch",
            "taxonomy": taxonomy,
            "market": market,
            "requested_count": len(requested_symbols) if requested_symbols else "all",
            "cache_hits": len(requested_symbols) - len(missing_symbols),
            "mapped_count": len(industry_map),
        })
        return industry_map

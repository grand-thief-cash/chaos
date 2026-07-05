"""市场数据服务，封装 PhoenixAClient 获取 OHLCV K 线数据。"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.log.logger import get_logger
from artemis.models.workbench import MarketDataQuery, normalize_dimensions
from artemis.services.workbench.providers import provider_registry

logger = get_logger("market_data_service")


def _build_phoenix_client(source: str | None = None) -> PhoenixAClient:
    """从配置构建 PhoenixAClient。source 指定数据源名称。"""
    dept = cfg_mgr.get_dept_services_for_source(source)
    if not dept or not dept.phoenixA:
        raise ValueError("phoenixA service not configured")
    cfg = dept.phoenixA
    return PhoenixAClient(
        host=cfg.host,
        port=cfg.port,
        logger=logger,
        timeout_seconds=getattr(cfg, "timeout_seconds", 30),
    )


def _sanitize_value(v: Any) -> Any:
    """将 NaN/inf 替换为 None，确保 JSON 可序列化。"""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _sanitize_bars(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """清洗 bars 数据中的 NaN/inf 值。"""
    return [{k: _sanitize_value(v) for k, v in bar.items()} for bar in bars]


def _resolve_symbol(client: PhoenixAClient, security_id: int, asset_type: str, market: str) -> str:
    """Resolve security_id → symbol via the securities registry, validating
    that the registry's asset_type/market match the request.

    Uses the targeted GET /api/v2/securities/{security_id} (O(1)) instead of
    pulling the full registry. The asset_type/market check is mandatory:
    cache_engine is keyed by (asset_type, market, period, adjust, symbol), so a
    mismatch between the request and the security's actual identity would route
    to the wrong cache bucket (e.g. an index security_id with asset_type=stock
    hitting a stock cache entry for the same symbol) — fail-closed here rather
    than rely on phoenixA's path-mismatch 400 to catch it after a cache hit.
    """
    info = client.get_security_by_id(security_id)
    if not info:
        raise ValueError(f"security_id {security_id} not found in security_registry")
    reg_asset = (info.get("asset_type") or "").strip()
    reg_market = (info.get("market") or "").strip()
    if reg_asset and reg_asset != asset_type:
        raise ValueError(
            f"asset_type mismatch: request={asset_type!r} but security_id {security_id} is {reg_asset!r}"
        )
    if reg_market and reg_market != market:
        raise ValueError(
            f"market mismatch: request={market!r} but security_id {security_id} is {reg_market!r}"
        )
    return info.get("symbol", "")


def _build_query(
    *,
    security_id: int,
    symbol: str,
    start_date: str,
    end_date: str,
    period: str,
    adjust: str,
    asset_type: str,
    market: str,
    source: str | None,
    use_cache: bool,
) -> MarketDataQuery:
    if not security_id:
        raise ValueError("security_id is required")
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    dims = normalize_dimensions(
        asset_type=asset_type,
        market=market,
        period=period,
        adjust=adjust,
    )
    return MarketDataQuery(
        security_id=security_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        asset_type=dims.asset_type,
        market=dims.market,
        period=dims.period,
        adjust=dims.adjust,
        source=source,
        use_cache=use_cache,
    )


def _fetch_provider_bars(query: MarketDataQuery) -> List[Dict[str, Any]]:
    provider = provider_registry.resolve(asset_type=query.asset_type, market=query.market)
    client = _build_phoenix_client(source=query.source)
    logger.info({
        "event": "provider_fetch",
        "provider": provider.name,
        "security_id": query.security_id,
        "symbol": query.symbol,
        "asset_type": query.asset_type,
        "market": query.market,
        "period": query.period,
        "adjust": query.adjust,
    })
    return provider.fetch_bars(client=client, query=query)


def get_market_bars(
    *,
    security_id: int,
    start_date: str,
    end_date: str,
    period: str = "daily",
    adjust: str = "nf",
    asset_type: str = "stock",
    market: str = "zh_a",
    source: str | None = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """获取 K 线 OHLCV 数据，支持本地 Arrow 缓存。

    Identity is security_id; symbol is resolved from the registry and used as
    the cache_engine physical key (§3.2 permanent-storage exception).

    Returns:
        {"security_id", "symbol", "period", "start_date", "end_date", "bars": [...]}
    """
    client = _build_phoenix_client(source=source)
    # Normalize dimensions BEFORE resolving so the registry compare uses
    # canonical values — a raw " stock " / "zh_a " from a direct API call
    # would otherwise falsely mismatch the registry's stripped asset_type.
    dims = normalize_dimensions(
        asset_type=asset_type, market=market, period=period, adjust=adjust,
    )
    symbol = _resolve_symbol(client, security_id, dims.asset_type, dims.market)

    query = _build_query(
        security_id=security_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        period=dims.period,
        adjust=dims.adjust,
        asset_type=dims.asset_type,
        market=dims.market,
        source=source,
        use_cache=use_cache,
    )
    provider = provider_registry.resolve(asset_type=query.asset_type, market=query.market)

    cache = None
    if query.use_cache:
        try:
            from artemis.engines.cache_engine import get_cache_engine
            cache = get_cache_engine()
            if cache is None:
                logger.info({"event": "cache_not_enabled", "security_id": query.security_id})
        except Exception:
            logger.warning({"event": "cache_init_failed", "security_id": query.security_id}, exc_info=True)

    if cache:
        logger.info({
            "event": "cache_attempt",
            "security_id": query.security_id, "symbol": query.symbol, "period": query.period,
            "start": query.start_date, "end": query.end_date, "adjust": query.adjust,
            "asset_type": query.asset_type, "market": query.market,
            "cache_dir": str(cache.storage.cache_dir),
        })

        def _fetcher(sym: str, cached_period: str, start: str, end: str, adj: str) -> List[Dict[str, Any]]:
            cached_query = query.model_copy(update={
                "symbol": sym,
                "period": cached_period,
                "start_date": start,
                "end_date": end,
                "adjust": adj,
            })
            logger.info({
                "event": "cache_miss_fetch_with_provider",
                "provider": provider.name,
                "symbol": sym,
                "period": cached_period,
                "start": start,
                "end": end,
                "adjust": adj,
            })
            return provider.fetch_bars(
                client=_build_phoenix_client(source=query.source),
                query=cached_query,
            )

        df = cache.get(
            symbol=query.symbol, period=query.period,
            start_date=query.start_date, end_date=query.end_date,
            asset_type=query.asset_type, market=query.market, adjust=query.adjust,
            use_cache=query.use_cache,
            data_fetcher=_fetcher,
        )
        if df is not None and not df.empty:
            logger.info({
                "event": "cache_hit",
                "security_id": query.security_id, "symbol": query.symbol, "period": query.period, "rows": len(df),
            })
            bars = _sanitize_bars(df.to_dict(orient="records"))
            return {
                "security_id": query.security_id,
                "symbol": query.symbol,
                "period": query.period,
                "start_date": query.start_date,
                "end_date": query.end_date,
                "bars": bars,
            }

    # Fallback: 直接调 PhoenixA
    logger.info({
        "event": "cache_fallback",
        "security_id": query.security_id, "symbol": query.symbol, "period": query.period,
        "reason": "no_cache_engine" if cache is None else "cache_miss_or_disabled",
        "provider": provider.name,
    })
    bars = _fetch_provider_bars(query)
    return {
        "security_id": query.security_id,
        "symbol": query.symbol,
        "period": query.period,
        "start_date": query.start_date,
        "end_date": query.end_date,
        "bars": _sanitize_bars(bars) if bars else [],
    }

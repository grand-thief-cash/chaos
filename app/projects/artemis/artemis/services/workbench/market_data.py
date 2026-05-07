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


def _build_query(
    *,
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
    if not symbol:
        raise ValueError("symbol is required")
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    dims = normalize_dimensions(
        asset_type=asset_type,
        market=market,
        period=period,
        adjust=adjust,
    )
    return MarketDataQuery(
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
        "symbol": query.symbol,
        "asset_type": query.asset_type,
        "market": query.market,
        "period": query.period,
        "adjust": query.adjust,
    })
    return provider.fetch_bars(client=client, query=query)


def get_market_bars(
    *,
    symbol: str,
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

    Returns:
        {"symbol", "period", "start_date", "end_date", "bars": [...]} 
    """
    query = _build_query(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        period=period,
        adjust=adjust,
        asset_type=asset_type,
        market=market,
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
                logger.info({"event": "cache_not_enabled", "symbol": query.symbol})
        except Exception:
            logger.warning({"event": "cache_init_failed", "symbol": query.symbol}, exc_info=True)

    if cache:
        logger.info({
            "event": "cache_attempt",
            "symbol": query.symbol, "period": query.period,
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
                "symbol": query.symbol, "period": query.period, "rows": len(df),
            })
            bars = _sanitize_bars(df.to_dict(orient="records"))
            return {
                "symbol": query.symbol,
                "period": query.period,
                "start_date": query.start_date,
                "end_date": query.end_date,
                "bars": bars,
            }

    # Fallback: 直接调 PhoenixA
    logger.info({
        "event": "cache_fallback",
        "symbol": query.symbol, "period": query.period,
        "reason": "no_cache_engine" if cache is None else "cache_miss_or_disabled",
        "provider": provider.name,
    })
    bars = _fetch_provider_bars(query)
    return {
        "symbol": query.symbol,
        "period": query.period,
        "start_date": query.start_date,
        "end_date": query.end_date,
        "bars": _sanitize_bars(bars) if bars else [],
    }

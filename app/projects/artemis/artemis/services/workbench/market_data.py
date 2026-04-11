"""市场数据服务，封装 PhoenixAClient 获取 OHLCV K 线数据。"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.log.logger import get_logger

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


def get_market_bars(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "daily",
    adjust: str = "nf",
    asset_type: str = "stock",
    market: str = "zh_a",
    source: str | None = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """获取 K 线 OHLCV 数据，支持本地 Arrow 缓存。

    Returns:
        {"symbol", "timeframe", "start_date", "end_date", "bars": [...]}
    """
    cache = None
    if use_cache:
        try:
            from artemis.engines.cache_engine import get_cache_engine
            cache = get_cache_engine()
            if cache is None:
                logger.info({"event": "cache_not_enabled", "symbol": symbol})
        except Exception:
            logger.warning({"event": "cache_init_failed", "symbol": symbol}, exc_info=True)

    if cache:
        logger.info({
            "event": "cache_attempt",
            "symbol": symbol, "period": timeframe,
            "start": start_date, "end": end_date, "adjust": adjust,
            "cache_dir": str(cache.storage.cache_dir),
        })

        def _fetcher(sym: str, period: str, start: str, end: str, adj: str) -> List[Dict[str, Any]]:
            client = _build_phoenix_client(source=source)
            return client.get_strategy_market_bars(
                symbol=sym, start_date=start, end_date=end,
                timeframe=period, adjust=adj,
            )

        df = cache.get(
            symbol=symbol, period=timeframe,
            start_date=start_date, end_date=end_date,
            asset_type=asset_type, market=market, adjust=adjust,
            use_cache=use_cache,
            data_fetcher=_fetcher,
        )
        if df is not None and not df.empty:
            logger.info({
                "event": "cache_hit",
                "symbol": symbol, "period": timeframe, "rows": len(df),
            })
            bars = _sanitize_bars(df.to_dict(orient="records"))
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "bars": bars,
            }

    # Fallback: 直接调 PhoenixA
    logger.info({
        "event": "cache_fallback",
        "symbol": symbol, "period": timeframe,
        "reason": "no_cache_engine" if cache is None else "cache_miss_or_disabled",
    })
    client = _build_phoenix_client(source=source)
    bars = client.get_strategy_market_bars(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        adjust=adjust,
    )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "bars": _sanitize_bars(bars) if bars else [],
    }

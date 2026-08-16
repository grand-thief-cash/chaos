"""Workbench API routes — market data + indicators + cache management."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from artemis.core import cfg_mgr
from artemis.log.logger import get_logger
from artemis.models.workbench import IndicatorsRequest, CompactRequest

logger = get_logger("workbench.routes")

router = APIRouter(prefix="/workbench", tags=["workbench"])

from artemis.api.http_gateway.t_trading_routes import router as t_trading_router  # noqa: E402
from artemis.api.http_gateway.valuation_routes import router as valuation_router  # noqa: E402

router.include_router(t_trading_router)
router.include_router(valuation_router)


def _indicator_warmup_start(start_date: str, period: str) -> str:
    """Return a conservative history start used only to seed indicators."""
    requested = date.fromisoformat(start_date[:10])
    calendar_days = {
        "weekly": 1800,
        "daily": 550,
        "min1": 45,
        "1min": 45,
        "min5": 45,
        "5min": 45,
        "min15": 90,
        "15min": 90,
        "min30": 120,
        "30min": 120,
        "min60": 180,
        "60min": 180,
    }.get(period, 550)
    return (requested - timedelta(days=calendar_days)).isoformat()


@router.get("/sources")
async def get_sources():
    """返回可用数据源列表。"""
    return cfg_mgr.available_sources()


@router.get("/data-options")
async def get_data_options():
    """返回 Workbench 数据维度选项。"""
    return cfg_mgr.data_options_config().model_dump()


@router.get("/market-data")
async def get_market_data(
    security_id: int,
    start_date: str,
    end_date: str,
    period: str = "daily",
    adjust: str = "nf",
    asset_type: str = "stock",
    market: str = "zh_a",
    source: str | None = None,
    use_cache: bool = True,
):
    """获取 K 线 OHLCV 数据。Identity is security_id."""
    from artemis.services.workbench import get_market_bars

    try:
        return get_market_bars(
            security_id=security_id,
            start_date=start_date,
            end_date=end_date,
            period=period,
            adjust=adjust,
            asset_type=asset_type,
            market=market,
            source=source,
            use_cache=use_cache,
        )
    except ValueError as e:
        logger.warning({"event": "market_data_validation_error", "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "market_data_failed", "error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/indicators")
async def list_indicators():
    """返回所有可用技术指标。"""
    from artemis.engines.indicator_engine import list_available_indicators

    return {"indicators": list_available_indicators()}


@router.post("/indicators")
async def compute_indicators(req: IndicatorsRequest):
    """计算技术指标。Identity is security_id."""
    import pandas as pd

    from artemis.engines.indicator_engine import compute_indicators as do_compute
    from artemis.services.workbench import get_market_bars

    try:
        target_market_data = get_market_bars(
            security_id=req.security_id,
            start_date=req.start_date,
            end_date=req.end_date,
            period=req.period,
            adjust=req.adjust,
            asset_type=req.asset_type,
            market=req.market,
            source=req.source,
        )
        target_bars = target_market_data["bars"]
        if not target_bars:
            raise ValueError("no bars for requested indicator range")

        # Technical indicators are continuous across sessions. Load preceding
        # bars for EMA/MACD/RSI/ATR state, then return only points aligned with
        # the user's requested bars. This matches brokerage-terminal behavior
        # at the open without backfilling or using future data.
        market_data = get_market_bars(
            security_id=req.security_id,
            start_date=_indicator_warmup_start(req.start_date, req.period),
            end_date=req.end_date,
            period=req.period,
            adjust=req.adjust,
            asset_type=req.asset_type,
            market=req.market,
            source=req.source,
        )
        df = pd.DataFrame(market_data["bars"])
        df["_indicator_time"] = pd.to_datetime(
            df["date"], errors="coerce", utc=True
        )
        df = (
            df.dropna(subset=["_indicator_time"])
            .sort_values("_indicator_time")
            .drop_duplicates(subset=["_indicator_time"], keep="last")
            .reset_index(drop=True)
        )

        indicator_requests = [r.model_dump() for r in req.indicators]
        full_series, meta = do_compute(df, indicator_requests)
        position_by_time = {
            value: index for index, value in enumerate(df["_indicator_time"])
        }
        target_times = pd.to_datetime(
            [item["date"] for item in target_bars],
            errors="coerce",
            utc=True,
        )
        positions = [position_by_time[value] for value in target_times]
        series = {
            key: [values[index] for index in positions]
            for key, values in full_series.items()
        }

        return {
            "security_id": req.security_id,
            "symbol": target_market_data.get("symbol", ""),
            "period": req.period,
            "indicators": series,
            "indicator_meta": meta,
            "warmup_bar_count": max(0, len(df) - len(target_bars)),
        }
    except ValueError as e:
        logger.warning({"event": "indicators_validation_error", "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "indicators_failed", "error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


# ── Cache API ─────────────────────────────────────────────────
# cache_engine is symbol-keyed (§3.2 permanent-storage exception); compaction
# operates on the physical symbol key directly.


@router.post("/cache/compact")
async def compact_cache(req: CompactRequest):
    """触发缓存 Compaction。必须指定 symbol，可选 period/asset_type/market/adjust。"""
    from artemis.engines.cache_engine import get_cache_engine

    cache = get_cache_engine()
    if not cache:
        raise HTTPException(status_code=404, detail="cache engine not enabled")

    lock = cache.compaction_lock
    if lock.is_compacting:
        raise HTTPException(
            status_code=503, detail="compaction already in progress",
            headers={"Retry-After": "30"},
        )

    if not lock.acquire_compaction(timeout=5):
        raise HTTPException(
            status_code=503, detail="cache is busy, retry later",
            headers={"Retry-After": "30"},
        )

    try:
        result = cache.compaction_manager.compact_symbol(
            symbol=req.symbol,
            period=req.period,
            asset_type=req.asset_type,
            market=req.market,
            adjust=req.adjust,
        )
        return {"results": [{"symbol": result.symbol, "period": result.period,
                             "bases_compacted": result.bases_compacted,
                             "inc_files_merged": result.inc_files_merged,
                             "total_rows": result.total_rows,
                             "duration_ms": result.duration_ms}]}
    finally:
        lock.release_compaction()


@router.get("/cache/stats")
async def cache_stats():
    """获取缓存统计信息。"""
    from artemis.engines.cache_engine import get_cache_engine

    cache = get_cache_engine()
    if not cache:
        raise HTTPException(status_code=404, detail="cache engine not enabled")

    cache_dir = cache.storage.cache_dir
    arrow_files = list(cache_dir.rglob("*.arrow")) if cache_dir.exists() else []
    total_size = sum(f.stat().st_size for f in arrow_files if f.is_file())

    return {
        "enabled": True,
        "cache_dir": str(cache_dir),
        "file_count": len(arrow_files),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
    }

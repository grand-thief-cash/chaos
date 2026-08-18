"""Ephemeral T-trading replay APIs for the Artemis Workbench."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from artemis.log.logger import get_logger
from artemis.models.t_trading import TBatchReplayRequest, TReplayRequest
from artemis.services.t_trading import NoMinuteDataError, run_batch_replay, run_replay

logger = get_logger("t_trading.routes")
router = APIRouter(prefix="/t-trading", tags=["t-trading"])

NEAREST_TRADE_DATE_WINDOW_DAYS = 45


@router.get("/nearest-trade-date")
async def nearest_trade_date(
    security_id: int = Query(gt=0),
    trade_date: date = Query(),
    direction: Literal["prev", "next"] = Query(),
):
    """Return the closest day that actually has daily bars for the security.

    Drives the UI day navigator so weekends/holidays/suspensions are skipped
    instead of surfacing a no-data error.
    """
    from artemis.services.workbench import get_market_bars

    if direction == "prev":
        start = (trade_date - timedelta(days=NEAREST_TRADE_DATE_WINDOW_DAYS)).isoformat()
        end = (trade_date - timedelta(days=1)).isoformat()
    else:
        start = (trade_date + timedelta(days=1)).isoformat()
        end = (trade_date + timedelta(days=NEAREST_TRADE_DATE_WINDOW_DAYS)).isoformat()
    try:
        data = get_market_bars(
            security_id=security_id,
            start_date=start,
            end_date=end,
            period="daily",
            adjust="nf",
            asset_type="stock",
            market="zh_a",
            use_cache=False,
        )
    except Exception as exc:
        logger.warning({"event": "nearest_trade_date_lookup_failed", "error": str(exc)})
        raise HTTPException(status_code=502, detail="trade-date lookup failed")
    # phoenixA_client renames trade_date -> date for cache compatibility.
    available = sorted({str(item["date"])[:10] for item in data.get("bars", [])})
    if not available:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no daily bars within {NEAREST_TRADE_DATE_WINDOW_DAYS} days "
                f"{'before' if direction == 'prev' else 'after'} {trade_date.isoformat()}"
            ),
        )
    picked = available[-1] if direction == "prev" else available[0]
    return {
        "security_id": security_id,
        "requested_trade_date": trade_date.isoformat(),
        "direction": direction,
        "trade_date": picked,
        "available_count": len(available),
    }


@router.get("/config")
async def get_t_trading_config():
    return {
        "persistence_modes": ["ephemeral"],
        "default_persistence_mode": "ephemeral",
        "periods": ["min1", "min5"],
        "adjustments": ["nf"],
        "signal_semantics": "signal_at_bar_close_evaluate_subsequent_bars",
        "execution_semantics": (
            "optional_decision_at_bar_close_fill_at_next_bar_open"
        ),
        "primary_evaluation": "forward_event_study_v1",
        "default_evaluation_horizons_bars": [1, 3, 6, 12],
        "default_evaluation_by_period": {
            "min1": {
                "horizons_bars": [1, 3, 5, 15],
                "primary_horizon_bars": 5,
            },
            "min5": {
                "horizons_bars": [1, 3, 6, 12],
                "primary_horizon_bars": 6,
            },
        },
        "execution_simulation_default": False,
        "result_storage": "none",
        "direction_modes": ["independent", "buy_first", "sell_first"],
        "strategies": [
            {
                "value": "causal_mean_reversion_v1",
                "label": "Z-score + RSI + VWAP 反转",
                "data_tier": "min1_or_min5_ohlcv",
            },
            {
                "value": "macd_volume_momentum_v1",
                "label": "MACD + 量能 + EMA 偏离回归",
                "data_tier": "min1_or_min5_ohlcv",
            },
            {
                "value": "macd_volume_regime_reversal_v1",
                "label": "MACD + 量能 + EMA + 不对称单边门控",
                "data_tier": "min1_or_min5_ohlcv",
            },
            {
                "value": "vwap_bollinger_reversion_v1",
                "label": "VWAP + Bollinger + 拒绝影线",
                "data_tier": "min1_or_min5_ohlcv",
            },
            {
                "value": "opening_range_breakout_v1",
                "label": "开盘区间 + 量能突破",
                "data_tier": "min1_or_min5_ohlcv",
            },
            {
                "value": "time_of_day_volume_momentum_v1",
                "label": "同分钟历史异常量能 + 动量",
                "data_tier": "min1_20d_same_minute",
            },
            {
                "value": "market_residual_reversal_v1",
                "label": "宽基指数残差反转",
                "data_tier": "synchronized_stock_index_bars",
                "requires": ["benchmark_security_id"],
            },
            {
                "value": "multi_timeframe_pullback_v1",
                "label": "日线/30分钟顺势回踩",
                "data_tier": "daily_min30_intraday",
            },
        ],
        "excluded_strategies": [
            {
                "value": "industry_residual_reversal",
                "reason": "AmazingData guide does not document industry-index minute K-lines",
            }
        ],
    }


@router.post("/replay")
async def replay(req: TReplayRequest):
    try:
        return run_replay(req)
    except NoMinuteDataError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NO_MINUTE_BARS",
                "message": "所选日期没有分钟行情，可能是周末、休市或停牌",
                "security_id": req.security_id,
                "trade_date": req.trade_date.isoformat(),
                "reason": str(exc),
            },
        )
    except ValueError as exc:
        logger.warning({"event": "t_replay_validation_error", "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "t_replay_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/batch")
async def batch_replay(req: TBatchReplayRequest):
    try:
        return run_batch_replay(req)
    except ValueError as exc:
        logger.warning({"event": "t_batch_validation_error", "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "t_batch_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/batch-replay", include_in_schema=False)
async def batch_replay_compat(req: TBatchReplayRequest):
    return await batch_replay(req)

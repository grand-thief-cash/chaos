"""Ephemeral T-trading replay APIs for the Artemis Workbench."""

from fastapi import APIRouter, HTTPException

from artemis.log.logger import get_logger
from artemis.models.t_trading import TBatchReplayRequest, TReplayRequest
from artemis.services.t_trading import NoMinuteDataError, run_batch_replay, run_replay

logger = get_logger("t_trading.routes")
router = APIRouter(prefix="/t-trading", tags=["t-trading"])


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
        "strategies": [
            {
                "value": "causal_mean_reversion_v1",
                "label": "Z-score + RSI + VWAP 反转",
                "data_tier": "min1_or_min5_ohlcv",
            },
            {
                "value": "macd_volume_momentum_v1",
                "label": "MACD + 成交量 + 分钟 EMA",
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
        raise HTTPException(status_code=400, detail=str(exc))
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

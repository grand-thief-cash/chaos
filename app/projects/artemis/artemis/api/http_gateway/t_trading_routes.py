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
        "periods": ["min5"],
        "adjustments": ["nf"],
        "execution_semantics": "decision_at_bar_close_fill_at_next_bar_open",
        "result_storage": "none",
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

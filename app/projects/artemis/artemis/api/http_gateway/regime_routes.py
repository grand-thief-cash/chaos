"""Regime 引擎 API 路由。"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from artemis.services import regime_service
from artemis.log.logger import get_logger

logger = get_logger("regime.routes")

router = APIRouter(prefix="/regime", tags=["regime"])


@router.post("/compute")
async def compute_regime(trade_date: Optional[str] = None, market: str = "zh_a"):
    """触发单日 regime 计算。"""
    if not trade_date:
        from datetime import date
        trade_date = date.today().strftime("%Y%m%d")
    try:
        return regime_service.compute_regime(trade_date, market)
    except Exception as e:
        logger.error({"event": "regime_compute_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill")
async def backfill(trading_dates: List[str]):
    """批量回填历史 regime。"""
    try:
        return regime_service.backfill(trading_dates)
    except Exception as e:
        logger.error({"event": "regime_backfill_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current")
async def get_current(market: str = "zh_a"):
    """获取最新 regime。"""
    result = regime_service.get_current(market)
    if result is None:
        raise HTTPException(status_code=404, detail="No regime computed yet")
    return result


@router.get("/history")
async def get_history(limit: int = 60):
    """历史 regime 序列。"""
    return regime_service.get_history(limit)


@router.get("/features")
async def get_features(trade_date: str):
    """查询指定日期 regime 特征。"""
    result = regime_service.get_features(trade_date)
    if result is None:
        raise HTTPException(status_code=404, detail="Features not found")
    return result


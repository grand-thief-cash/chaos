"""因子引擎 API 路由。"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from artemis.services import factor_service
from artemis.log.logger import get_logger

logger = get_logger("factor.routes")

router = APIRouter(prefix="/factors", tags=["factors"])


@router.post("/compute/full")
async def compute_factors_full(market: str = "zh_a", as_of_date: Optional[str] = None):
    """触发全量因子计算。"""
    if not as_of_date:
        from datetime import date
        as_of_date = date.today().strftime("%Y%m%d")
    try:
        return factor_service.compute_full(as_of_date, market)
    except Exception as e:
        logger.error({"event": "factor_compute_full_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compute/incremental")
async def compute_factors_incremental(symbols: List[str], as_of_date: Optional[str] = None, market: str = "zh_a"):
    """增量因子计算。"""
    if not as_of_date:
        from datetime import date
        as_of_date = date.today().strftime("%Y%m%d")
    try:
        return factor_service.compute_incremental(symbols, as_of_date, market)
    except Exception as e:
        logger.error({"event": "factor_compute_incr_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot")
async def get_factor_snapshot(symbol: str, as_of_date: str, market: str = "zh_a"):
    """查询单股因子快照。"""
    result = factor_service.get_snapshot(symbol, as_of_date, market)
    if result is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return result


@router.get("/rank")
async def get_factor_ranking(factor_name: str, as_of_date: str, market: str = "zh_a", top_n: int = 50):
    """全市场因子排名。"""
    return factor_service.get_ranking(factor_name, as_of_date, market, top_n)


@router.get("/meta")
async def get_factor_meta():
    """获取所有因子元数据。"""
    return factor_service.get_meta()


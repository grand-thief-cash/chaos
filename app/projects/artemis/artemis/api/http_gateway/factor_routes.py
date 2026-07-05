"""因子引擎 API 路由。

Identity is security_id (refactor §3.6, no dual-track). Responses are
security_id-native with symbol kept as decoration where it already exists
in the store.

Strict identity (Phase 1/3 pattern): a present-but-empty / non-numeric /
zero / empty-token security_id(s) → 400 (never silently degrades).
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from artemis.api.http_gateway._identity import _parse_security_id, _parse_security_ids
from artemis.services import factor_service
from artemis.log.logger import get_logger

logger = get_logger("factor.routes")

router = APIRouter(prefix="/factors", tags=["factors"])


@router.post("/compute/full")
async def compute_factors_full(market: str = "zh_a", as_of_date: Optional[str] = None, source: Optional[str] = None):
    """触发全量因子计算。"""
    if not as_of_date:
        from datetime import date
        as_of_date = date.today().strftime("%Y%m%d")
    try:
        return factor_service.compute_full(as_of_date, market, source=source)
    except Exception as e:
        logger.error({"event": "factor_compute_full_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compute/incremental")
async def compute_factors_incremental(
    as_of_date: Optional[str] = None,
    market: str = "zh_a",
    source: Optional[str] = None,
    security_ids: Optional[str] = Query(None, description="comma-separated security_ids (required)"),
):
    """增量因子计算。security_ids is required (comma-separated query param)."""
    if not as_of_date:
        from datetime import date
        as_of_date = date.today().strftime("%Y%m%d")
    sids = _parse_security_ids(security_ids)
    if sids is None:
        raise HTTPException(status_code=400, detail="security_ids is required")
    try:
        return factor_service.compute_incremental(
            security_ids=sids,
            as_of_date=as_of_date,
            market=market,
            source=source,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "factor_compute_incr_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot")
async def get_factor_snapshot(
    as_of_date: str,
    security_id: Optional[str] = Query(None),
    market: str = "zh_a",
    source: Optional[str] = None,
):
    """查询单股因子快照。security_id is required."""
    sid = _parse_security_id(security_id)
    if sid is None:
        raise HTTPException(status_code=400, detail="security_id is required")
    try:
        result = factor_service.get_snapshot(
            security_id=sid,
            as_of_date=as_of_date, market=market, source=source,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "factor_snapshot_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return result


@router.get("/rank")
async def get_factor_ranking(factor_name: str, as_of_date: str, market: str = "zh_a", top_n: int = 50, source: Optional[str] = None):
    """全市场因子排名。Rows are keyed by security_id with symbol decoration (Phase 4)."""
    return factor_service.get_ranking(factor_name, as_of_date, market, top_n, source=source)


@router.get("/meta")
async def get_factor_meta():
    """获取所有因子元数据。"""
    return factor_service.get_meta()


@router.get("/availability")
async def get_factor_availability(refresh: bool = False, source: Optional[str] = None):
    """获取因子可用性分析。"""
    try:
        return factor_service.get_availability(refresh=refresh, source=source)
    except Exception as e:
        logger.error({"event": "factor_availability_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

"""因子引擎 API 路由。

Phase 4: identity is security_id (refactor §3.6). symbol/symbols remain as
convenience input (resolved to security_id inside factor_service, §8.bis-5)
so cthulhu keeps working until its factor page migrates. Responses are
security_id-native with symbol kept as decoration.

Strict identity (Phase 1/3 pattern): a present-but-empty / non-numeric / zero /
empty-token security_id(s) → 400; an unresolvable symbol or a partial symbols
batch → 400 (never silently computes a subset).
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from artemis.services import factor_service
from artemis.log.logger import get_logger

logger = get_logger("factor.routes")

router = APIRouter(prefix="/factors", tags=["factors"])


def _parse_security_ids(raw: Optional[str]) -> Optional[List[int]]:
    """Parse a comma-separated security_ids query string → list[int] (strict).

    None (absent) → None. A present value is parsed strictly: empty tokens,
    non-numeric tokens, non-positive ids → 400.
    """
    if raw is None:
        return None
    out: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            raise HTTPException(status_code=400, detail="security_ids contains an empty token")
        try:
            v = int(token)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"invalid security_id token: {token!r}")
        if v <= 0:
            raise HTTPException(status_code=400, detail=f"security_id must be a positive integer, got {v}")
        out.append(v)
    if not out:
        raise HTTPException(status_code=400, detail="security_ids is empty")
    return out


def _parse_security_id(raw: Optional[str]) -> Optional[int]:
    """Parse a singular security_id query string → int (strict).

    None (absent) → None. A present value is parsed strictly: empty,
    non-numeric, or non-positive → 400 — never silently treated as absent
    (which would let an explicit empty identity degrade downstream). Mirrors
    `_parse_security_ids` so both identity shapes return a uniform 400 +
    `{"detail": "..."}` envelope instead of FastAPI's 422 validation array.
    """
    if raw is None:
        return None
    token = raw.strip()
    if not token:
        raise HTTPException(status_code=400, detail="security_id is empty")
    try:
        v = int(token)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid security_id: {token!r}")
    if v <= 0:
        raise HTTPException(status_code=400, detail=f"security_id must be a positive integer, got {v}")
    return v


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
    symbols: Optional[List[str]] = None,
    as_of_date: Optional[str] = None,
    market: str = "zh_a",
    source: Optional[str] = None,
    security_ids: Optional[str] = Query(None, description="comma-separated security_ids (primary)"),
):
    """增量因子计算。

    `security_ids` (query, primary) and `symbols` (body, convenience) are
    mutually-resolvable: pass either. cthulhu posts a bare JSON array body of
    symbols; security_id-native callers use the query param. At least one is
    required. A partial symbols batch (any entry unresolved) → 400.
    """
    if not as_of_date:
        from datetime import date
        as_of_date = date.today().strftime("%Y%m%d")
    try:
        return factor_service.compute_incremental(
            security_ids=_parse_security_ids(security_ids),
            symbols=symbols,
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
    symbol: Optional[str] = None,
    market: str = "zh_a",
    source: Optional[str] = None,
):
    """查询单股因子快照。security_id is primary; symbol is convenience (Phase 4)."""
    sid = _parse_security_id(security_id)
    if sid is None and not symbol:
        raise HTTPException(status_code=400, detail="security_id or symbol is required")
    try:
        result = factor_service.get_snapshot(
            security_id=sid, symbol=symbol,
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

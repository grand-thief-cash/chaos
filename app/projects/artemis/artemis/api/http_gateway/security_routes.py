"""General securities lookup routes - /securities/* endpoints.

A general capability shared across features (BI DuPont, workbench, ...), not
BI-specific. cthulhu -> artemis /securities/* -> phoenixA /api/v2/securities/*.

  GET /securities            search by q (symbol exact OR name contains) +
                             legacy name/symbol/exchange/status filters
  GET /securities/{id}       fetch one by security_id

Identity is security_id downstream (e.g. /bi/dupont/{security_id}); these
routes only resolve the user-facing name/symbol -> security_id question. Strict
identity on the by-id path mirrors /bi routes (present-but-bad id -> 400).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from artemis.api.http_gateway._identity import _parse_security_id
from artemis.log.logger import get_logger
from artemis.services.securities import SecuritiesService

logger = get_logger("security.routes")
router = APIRouter(tags=["securities"])
service = SecuritiesService()


@router.get("/securities")
async def list_securities(
    q: Optional[str] = Query(None, description="名称或代码: symbol 精确(大小写不敏感) OR name 模糊包含, 满足任一即可"),
    market: str = Query("zh_a"),
    asset_type: str = Query("stock"),
    exchange: Optional[str] = Query(None, description="交易所, 逗号分隔多值, 如 SZ,SH"),
    name: Optional[str] = Query(None, description="legacy: name 模糊包含"),
    symbol: Optional[str] = Query(None, description="legacy: symbol 精确"),
    status: Optional[str] = Query(None, description="默认不过滤; 传 active/delisted 等"),
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    try:
        return service.list_securities(
            q=q, market=market, asset_type=asset_type, exchange=exchange,
            name=name, symbol=symbol, status=status, limit=limit, offset=offset,
        )
    except Exception as exc:
        logger.error({"event": "securities_list_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/securities/{security_id}")
async def get_security(security_id: str):
    sid = _parse_security_id(security_id)
    if sid is None:
        raise HTTPException(status_code=400, detail="security_id is required")
    try:
        return service.get_security(sid)
    except ValueError as exc:
        logger.warning({"event": "security_not_found", "security_id": sid, "error": str(exc)})
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "security_get_failed", "security_id": sid, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")

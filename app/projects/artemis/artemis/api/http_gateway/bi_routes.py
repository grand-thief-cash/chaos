"""Lightweight BI routes — /bi/* endpoints.

Thin passthroughs to phoenixA raw data APIs, with optional YoY/QoQ
computation for financial queries.

Architecture: cthulhu → artemis /bi/* → phoenixA /api/v2/*

Identity is security_id (refactor §3.6, no dual-track). Query routes accept
``security_id``/``security_ids``; the two single-identity path routes
(``/catalog/securities/{security_id}/datasets/summary``,
``/dupont/{security_id}``) take ``{security_id}`` in the path.

Strict identity (Phase 1/3 pattern): a present-but-empty / non-numeric / zero /
empty-token security_id(s) → 400, never silently degrades to an unfiltered
query. ValueError from the service layer (bad identity) → 400.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Literal, Optional

from artemis.api.http_gateway._identity import _parse_security_id, _parse_security_ids
from artemis.log.logger import get_logger
from artemis.models.metric_definitions import METRIC_DEFINITIONS
from artemis.services.bi import BIService
from artemis.services.securities import SecuritiesService

logger = get_logger("bi.routes")
router = APIRouter(prefix="/bi", tags=["bi"])
service = BIService()
# /bi/securities delegates to the general SecuritiesService (same impl as
# /securities) for back-compat; new callers should use /securities.
securities_service = SecuritiesService()


@router.get("/securities", deprecated=True)
async def list_securities(
    market: str = Query("zh_a"),
    asset_type: str = Query("stock"),
    exchange: str | None = Query(None),
    name: str | None = Query(None),
    q: str | None = Query(None, description="forward-compat: unified name/symbol search term"),
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Deprecated: use GET /securities instead. Delegates to the same impl."""
    try:
        return securities_service.list_securities(
            q=q, market=market, asset_type=asset_type, exchange=exchange,
            name=name, limit=limit, offset=offset,
        )
    except Exception as exc:
        logger.error({"event": "bi_list_securities_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/catalog/datasets")
async def list_datasets(source: str | None = Query(None)):
    try:
        return service.list_datasets(source=source)
    except Exception as exc:
        logger.error({"event": "bi_list_datasets_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/catalog/datasets/{dataset}/fields")
async def discover_fields(
    dataset: str,
    source: str | None = Query(None),
    type: str | None = Query(None),
    search: str | None = Query(None),
    include: str | None = Query(None),
):
    try:
        return service.discover_fields(
            dataset, source=source, data_type=type, search=search, include=include,
        )
    except Exception as exc:
        logger.error({"event": "bi_discover_fields_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/catalog/enums/{enum_name}")
async def get_enum(enum_name: str, source: str | None = Query(None)):
    try:
        return service.get_enum(enum_name, source=source)
    except Exception as exc:
        logger.error({"event": "bi_get_enum_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/catalog/securities/{security_id}/datasets/summary")
async def get_security_coverage(security_id: str, market: str = Query("zh_a")):
    sid = _parse_security_id(security_id)
    if sid is None:
        raise HTTPException(status_code=400, detail="security_id is required")
    try:
        return service.get_security_coverage(security_id=sid, market=market)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "bi_security_coverage_failed", "security_id": sid, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/financial/{source}/{statement_type}")
async def query_financial(
    source: str,
    statement_type: str,
    security_id: Optional[str] = Query(None),
    security_ids: Optional[str] = Query(None),
    market: str = Query("zh_a"),
    fields: str | None = Query(None),
    format: str = Query("flat"),
    period_start: str | None = Query(None),
    period_end: str | None = Query(None),
    report_type: str | None = Query(None),
    statement_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
):
    try:
        return service.query_financial(
            source=source, statement_type=statement_type,
            security_id=_parse_security_id(security_id), security_ids=_parse_security_ids(security_ids),
            market=market, fields=fields,
            format=format, period_start=period_start, period_end=period_end,
            report_type=report_type, statement_code=statement_code,
            page=page, page_size=page_size,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "bi_query_financial_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/corporate-action/{source}/{action_type}")
async def query_corporate_action(
    source: str,
    action_type: str,
    security_id: Optional[str] = Query(None),
    security_ids: Optional[str] = Query(None),
    market: str = Query("zh_a"),
    fields: str | None = Query(None),
    format: str = Query("flat"),
    period_start: str | None = Query(None),
    period_end: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
):
    try:
        return service.query_corporate_action(
            source=source, action_type=action_type,
            security_id=_parse_security_id(security_id), security_ids=_parse_security_ids(security_ids),
            market=market, fields=fields,
            format=format, period_start=period_start, period_end=period_end,
            page=page, page_size=page_size,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "bi_query_corp_action_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/equity-structure/{source}")
async def query_equity_structure(
    source: str,
    security_id: Optional[str] = Query(None),
    security_ids: Optional[str] = Query(None),
    market: str = Query("zh_a"),
    fields: str | None = Query(None),
    format: str = Query("flat"),
    change_start: str | None = Query(None),
    change_end: str | None = Query(None),
    current_only: bool | None = Query(None),
    valid_only: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
):
    try:
        return service.query_equity_structure(
            source=source,
            security_id=_parse_security_id(security_id), security_ids=_parse_security_ids(security_ids),
            market=market,
            fields=fields, format=format, change_start=change_start,
            change_end=change_end, current_only=current_only, valid_only=valid_only,
            page=page, page_size=page_size,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "bi_query_equity_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/meta/metrics")
async def get_metric_definitions():
    """Get BI metric definitions (preserved from old bi_engine)."""
    try:
        return {
            "version": "1.0.0",
            "metrics": METRIC_DEFINITIONS,
        }
    except Exception as exc:
        logger.error({"event": "bi_get_metrics_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/dupont/{security_id}")
async def get_dupont_analysis(
    security_id: str,
    source: str = Query("amazing_data"),
    market: str = Query("zh_a"),
    statement_code: str = Query("1", description="1=合并, 6=母公司"),
    period_kind: Literal["annual", "single_quarter", "ytd", "ttm"] = Query("ttm", description="年度/单季度/年初至今/滚动12个月(默认)"),
    target_reporting_period: str | None = Query(None, description="指定目标报告期YYYY-MM-DD，省略取最新可用"),
    extrapolate_q4: bool = Query(False, description="仅当period_kind=ytd且target_period是Q3时生效，按Q3YTD×4/3外推全年预测"),
):
    """DuPont decomposition: ttm(默认)/annual/single_quarter/ytd; Q3YTD可外推全年."""
    sid = _parse_security_id(security_id)
    if sid is None:
        raise HTTPException(status_code=400, detail="security_id is required")
    try:
        return service.get_dupont_analysis(
            security_id=sid, source=source, market=market,
            statement_code=statement_code, period_kind=period_kind,
            target_reporting_period=target_reporting_period,
            extrapolate_q4=extrapolate_q4,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        # ValueError from dupont = "no financial data for security_id" → 404
        logger.warning({"event": "bi_dupont_no_data", "security_id": sid, "error": str(exc)})
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "bi_dupont_failed", "security_id": sid, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")

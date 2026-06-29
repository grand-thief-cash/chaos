"""Lightweight BI routes — /bi/* endpoints.

Replaces the old bi_routes.py (dashboard/dupont/quality/insight/peer/metrics).
The new routes are thin passthroughs to phoenixA raw data APIs, with optional
YoY/QoQ computation for financial queries.

Architecture: cthulhu → artemis /bi/* → phoenixA /api/v2/*
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from artemis.log.logger import get_logger
from artemis.models.metric_definitions import METRIC_DEFINITIONS
from artemis.services.bi_simple_service import BISimpleService

logger = get_logger("bi_simple.routes")
router = APIRouter(prefix="/bi", tags=["bi"])
service = BISimpleService()


@router.get("/securities")
async def list_securities(
    market: str = Query("zh_a"),
    asset_type: str = Query("stock"),
    exchange: str | None = Query(None),
    name: str | None = Query(None),
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    try:
        return service.list_securities(
            market=market, asset_type=asset_type, exchange=exchange,
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


@router.get("/catalog/securities/{symbol}/datasets/summary")
async def get_symbol_coverage(symbol: str, market: str = Query("zh_a")):
    try:
        return service.get_symbol_coverage(symbol, market=market)
    except Exception as exc:
        logger.error({"event": "bi_symbol_coverage_failed", "symbol": symbol, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/financial/{source}/{statement_type}")
async def query_financial(
    source: str,
    statement_type: str,
    symbol: str | None = Query(None),
    symbols: str | None = Query(None),
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
            symbol=symbol, symbols=symbols, market=market, fields=fields,
            format=format, period_start=period_start, period_end=period_end,
            report_type=report_type, statement_code=statement_code,
            page=page, page_size=page_size,
        )
    except Exception as exc:
        logger.error({"event": "bi_query_financial_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/corporate-action/{source}/{action_type}")
async def query_corporate_action(
    source: str,
    action_type: str,
    symbol: str | None = Query(None),
    symbols: str | None = Query(None),
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
            symbol=symbol, symbols=symbols, market=market, fields=fields,
            format=format, period_start=period_start, period_end=period_end,
            page=page, page_size=page_size,
        )
    except Exception as exc:
        logger.error({"event": "bi_query_corp_action_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/equity-structure/{source}")
async def query_equity_structure(
    source: str,
    symbol: str | None = Query(None),
    symbols: str | None = Query(None),
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
            source=source, symbol=symbol, symbols=symbols, market=market,
            fields=fields, format=format, change_start=change_start,
            change_end=change_end, current_only=current_only, valid_only=valid_only,
            page=page, page_size=page_size,
        )
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


@router.get("/dupont/{symbol}")
async def get_dupont_analysis(
    symbol: str,
    source: str = Query("amazing_data"),
    market: str = Query("zh_a"),
    statement_code: str = Query("1", description="1=合并, 6=母公司"),
    period_kind: Literal["annual", "single_quarter", "ytd", "ttm"] = Query("ttm", description="年度/单季度/年初至今/滚动12个月(默认)"),
    target_reporting_period: str | None = Query(None, description="指定目标报告期YYYY-MM-DD，省略取最新可用"),
    extrapolate_q4: bool = Query(False, description="仅当period_kind=ytd且target_period是Q3时生效，按Q3YTD×4/3外推全年预测"),
):
    """DuPont decomposition: ttm(默认)/annual/single_quarter/ytd; Q3YTD可外推全年."""
    try:
        return service.get_dupont_analysis(
            symbol=symbol, source=source, market=market,
            statement_code=statement_code, period_kind=period_kind,
            target_reporting_period=target_reporting_period,
            extrapolate_q4=extrapolate_q4,
        )
    except ValueError as exc:
        logger.warning({"event": "bi_dupont_no_data", "symbol": symbol, "error": str(exc)})
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "bi_dupont_failed", "symbol": symbol, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")

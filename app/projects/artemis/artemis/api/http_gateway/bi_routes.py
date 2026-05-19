from __future__ import annotations

from fastapi import APIRouter, HTTPException

from artemis.log.logger import get_logger
from artemis.models.bi import (
    BIDashboardResponse,
    BIDupontResponse,
    BIInsightResponse,
    BIMetricsMetaResponse,
    BIPeerComparisonRequest,
    BIPeerComparisonResponse,
    BIQualityResponse,
    BISecuritySearchResponse,
)
from artemis.services.bi_service import BIService

logger = get_logger("bi.routes")
router = APIRouter(prefix="/bi", tags=["bi"])
service = BIService()


@router.get("/search/securities", response_model=BISecuritySearchResponse)
async def search_securities(query: str, market: str = "zh_a", limit: int = 20):
    try:
        return service.search_securities(query=query, market=market, limit=limit)
    except Exception as exc:  # pragma: no cover - route safety net
        logger.error({"event": "bi_search_securities_failed", "query": query, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/financial/company/{symbol}/dashboard", response_model=BIDashboardResponse)
async def get_company_dashboard(
    symbol: str,
    as_of_date: str,
    market: str = "zh_a",
    source: str = "amazing_data",
):
    try:
        return service.get_company_dashboard(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
    except ValueError as exc:
        logger.warning({"event": "bi_dashboard_validation_error", "symbol": symbol, "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - route safety net
        logger.error({"event": "bi_dashboard_failed", "symbol": symbol, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/financial/company/{symbol}/dupont", response_model=BIDupontResponse)
async def get_company_dupont(
    symbol: str,
    as_of_date: str,
    market: str = "zh_a",
    source: str = "amazing_data",
):
    try:
        return service.get_company_dupont(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
    except ValueError as exc:
        logger.warning({"event": "bi_dupont_validation_error", "symbol": symbol, "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - route safety net
        logger.error({"event": "bi_dupont_failed", "symbol": symbol, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/financial/company/{symbol}/quality", response_model=BIQualityResponse)
async def get_company_quality(
    symbol: str,
    as_of_date: str,
    market: str = "zh_a",
    source: str = "amazing_data",
):
    try:
        return service.get_company_quality(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
    except ValueError as exc:
        logger.warning({"event": "bi_quality_validation_error", "symbol": symbol, "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - route safety net
        logger.error({"event": "bi_quality_failed", "symbol": symbol, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/financial/peer-comparison", response_model=BIPeerComparisonResponse)
async def get_peer_comparison(req: BIPeerComparisonRequest):
    try:
        return service.get_peer_comparison(req)
    except ValueError as exc:
        logger.warning({"event": "bi_peer_comparison_validation_error", "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - route safety net
        logger.error({"event": "bi_peer_comparison_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/financial/company/{symbol}/insight", response_model=BIInsightResponse)
async def get_company_insight(
    symbol: str,
    as_of_date: str,
    market: str = "zh_a",
    source: str = "amazing_data",
):
    try:
        return service.get_company_insight(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
    except ValueError as exc:
        logger.warning({"event": "bi_insight_validation_error", "symbol": symbol, "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - route safety net
        logger.error({"event": "bi_insight_failed", "symbol": symbol, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/meta/metrics", response_model=BIMetricsMetaResponse)
async def get_metric_definitions():
    try:
        return service.get_metric_definitions()
    except Exception as exc:  # pragma: no cover - route safety net
        logger.error({"event": "bi_metric_definitions_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")



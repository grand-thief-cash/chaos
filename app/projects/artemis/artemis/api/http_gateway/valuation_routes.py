"""Point-in-time, explainable valuation-matrix APIs."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from artemis.log.logger import get_logger
from artemis.models.valuation import ValuationAnalyzeRequest, ValuationHistoryRequest
from artemis.services.valuation import (
    ValuationDataError,
    analyze_valuation,
    replay_valuation_history,
    valuation_eligibility,
)
from artemis.services.valuation.service import SCENARIO_DEFINITIONS


logger = get_logger("valuation.routes")
router = APIRouter(prefix="/valuation", tags=["valuation-matrix"])


@router.get("/config")
async def get_valuation_config():
    return {
        "supported_market": "zh_a",
        "scenarios": ["bear", "base", "bull"],
        "scenario_definitions": SCENARIO_DEFINITIONS,
        "methods": [
            {"code": "forward_pe", "label": "Forward PE", "default_weight": 0.40},
            {"code": "pb_roe", "label": "PB / ROE", "default_weight": 0.30},
            {"code": "ev_ebitda", "label": "EV / EBITDA", "default_weight": 0.20},
            {"code": "dcf", "label": "FCFF DCF", "default_weight": 0.10},
        ],
        "weight_semantics": "diagnostic in primary_with_cross_checks; headline in weighted_blend",
        "aggregation_policy": {
            "high_growth": {
                "mode": "primary_with_cross_checks",
                "primary": "forward_pe",
                "cross_checks": ["ev_ebitda", "dcf"],
                "guardrail": "pb_roe",
                "diagnostic_weights": {
                    "forward_pe": 0.70, "pb_roe": 0.05,
                    "ev_ebitda": 0.15, "dcf": 0.10,
                },
            },
            "balanced": {"mode": "weighted_blend"},
        },
        "forward_pe_sensitivity": "target-year EPS scenarios crossed with PE scenarios (3x3)",
        "price_reference_policy": {
            "framework": "scenario_reference_not_target_price",
            "headline": "low/base/high consensus anchors from the primary method",
            "market_implied": "reverse-solve the assumptions embedded in market price",
            "margin_of_safety": "user-selected observation discount; never a guaranteed buy price",
            "tail_stress": "not available until thesis-break assumptions are modelled explicitly",
        },
        "confidence_semantics": "data/model-structure score; not a return probability or recommendation strength",
        "history_quantiles": [0.25, 0.50, 0.75],
        "point_in_time_rule": (
            "price_date <= information_as_of; financial announcement_date <= information_as_of; "
            "consensus snapshot_date <= information_as_of"
        ),
        "consensus_semantics": "observed_on_fetch_date_no_synthetic_history",
        "free_source_policy": {
            "concurrency": 1,
            "default_interval_seconds": 2.0,
            "jitter_seconds": 0.8,
            "retry_attempts": 3,
        },
    }


@router.get("/eligibility")
async def get_valuation_eligibility(
    security_id: int = Query(gt=0),
    valuation_date: date | None = Query(default=None),
):
    return valuation_eligibility(
        security_id=security_id,
        valuation_date=valuation_date,
    )


@router.post("/analyze")
async def post_valuation_analyze(req: ValuationAnalyzeRequest):
    try:
        return analyze_valuation(req)
    except ValuationDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "valuation_analyze_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="valuation analysis failed")


@router.post("/history")
async def post_valuation_history(req: ValuationHistoryRequest):
    try:
        return replay_valuation_history(req)
    except ValuationDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error({"event": "valuation_history_failed", "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="valuation history replay failed")

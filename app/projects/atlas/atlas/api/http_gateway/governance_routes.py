from fastapi import APIRouter, HTTPException, Request
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ResearchReportType = Literal[
    "stock",
    "industry",
    "macro",
    "new_stock",
    "strategy",
    "morning_report",
]

router = APIRouter(prefix="/api/v1/atlas-kg", tags=["atlas-governance"])


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_size: int = Field(default=120, ge=1, le=2000)
    report_types: list[ResearchReportType] = Field(min_length=1)
    published_from: str | None = None
    published_to: str | None = None


class SemanticPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    discovery_run_id: str
    version: str = Field(pattern=r"^atlas-semantic-v\d{4,}$")


class CrosswalkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_scheme: str = Field(min_length=1, max_length=80)
    target_scheme: str = Field(min_length=1, max_length=80)


class CrosswalkPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    crosswalk_run_id: str
    version: str = Field(pattern=r"^atlas-semantic-v\d{4,}$")


@router.post("/discovery-runs")
async def create_discovery_run(payload: DiscoveryRequest, request: Request):
    if request.app.state.runtime.discovery_orchestrator is None:
        raise HTTPException(status_code=503, detail="discovery model adapter is not configured")
    return await request.app.state.runtime.discovery_orchestrator.run(payload)


@router.put("/discovery-runs/{run_id}/review")
async def review_discovery_run(run_id: str, payload: dict, request: Request):
    if request.app.state.runtime.discovery_orchestrator is None:
        raise HTTPException(status_code=503, detail="discovery model adapter is not configured")
    try:
        return await request.app.state.runtime.discovery_orchestrator.review(
            run_id, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/semantic-versions:publish")
async def publish_semantic_version(payload: SemanticPublishRequest, request: Request):
    if request.app.state.runtime.discovery_orchestrator is None:
        raise HTTPException(status_code=503, detail="discovery model adapter is not configured")
    try:
        return await request.app.state.runtime.discovery_orchestrator.publish(
            payload.discovery_run_id, payload.version
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/crosswalk-runs")
async def create_crosswalk_run(payload: CrosswalkRequest, request: Request):
    if request.app.state.runtime.crosswalk_service is None:
        raise HTTPException(status_code=503, detail="crosswalk model adapter is not configured")
    try:
        return await request.app.state.runtime.crosswalk_service.run_schemes(
            payload.source_scheme, payload.target_scheme
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/crosswalk-runs:required")
async def create_required_crosswalk_runs(request: Request):
    if request.app.state.runtime.crosswalk_service is None:
        raise HTTPException(
            status_code=503,
            detail="crosswalk model adapter is not configured",
        )
    try:
        results = await request.app.state.runtime.crosswalk_service.run_required()
        return {"count": len(results), "runs": results}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/crosswalk-runs/{run_id}/review")
async def review_crosswalk_run(run_id: str, payload: dict, request: Request):
    if request.app.state.runtime.crosswalk_service is None:
        raise HTTPException(
            status_code=503,
            detail="crosswalk model adapter is not configured",
        )
    try:
        return await request.app.state.runtime.crosswalk_service.review(
            run_id, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/crosswalk-semantic-versions:publish")
async def publish_crosswalk_semantic_version(
    payload: CrosswalkPublishRequest,
    request: Request,
):
    if request.app.state.runtime.crosswalk_service is None:
        raise HTTPException(
            status_code=503,
            detail="crosswalk model adapter is not configured",
        )
    try:
        return await request.app.state.runtime.crosswalk_service.publish(
            payload.crosswalk_run_id, payload.version
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from atlas.models import ResearchReport
from atlas.application.report_consumer import ExtractionBatchRequest

router = APIRouter(prefix="/api/v1/atlas-kg", tags=["atlas-extraction"])


class ManualExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: ResearchReport
    semantic_version: str | None = None


@router.post("/extractions")
async def create_extraction(payload: ManualExtractionRequest, request: Request):
    runtime = request.app.state.runtime
    semantic = runtime.semantic_registry.get(payload.semantic_version)
    profile = semantic.report_profile(payload.report.report_type)
    run = await runtime.knowledge_production_orchestrator.run_document(
        payload.report,
        semantic_config=semantic.payload,
        report_profile=profile,
    )
    return {"run": run.model_dump(mode="json"), "accepted": run.error_code is None}


@router.post("/extraction-batches")
async def create_extraction_batch(payload: ExtractionBatchRequest, request: Request):
    runs = await request.app.state.runtime.report_consumer.run(payload)
    return {
        "count": len(runs),
        "runs": [run.model_dump(mode="json") for run in runs],
    }


@router.get("/extraction-runs/{run_id}")
async def get_extraction_run(run_id: str, request: Request):
    return await request.app.state.runtime.phoenixa.get_extraction_run(run_id)

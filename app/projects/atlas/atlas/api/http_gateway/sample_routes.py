from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from atlas.core.sample_task_registry import sample_identity_key

router = APIRouter(prefix="/api/v1/atlas-kg", tags=["atlas-sample"])


class SampleRunRequest(BaseModel):
    """Sample request body. May arrive bare (UI) or wrapped as cronjob {meta, body}."""
    model_config = ConfigDict(extra="allow")
    # sample_size=0 means "all available documents" (full scan). Useful for
    # small test environments where you want exhaustive coverage.
    # A small, subtype-balanced pilot is cheaper and more informative than a
    # 120-document first pass. Use sample_seed for reproducible later rounds.
    sample_size: int = Field(default=24, ge=0, le=5000)
    report_types: list[str] = Field(min_length=1)
    published_from: str | None = None
    published_to: str | None = None
    sample_seed: int = Field(default=0, ge=0)
    force: bool = False


def _parse_cronjob_envelope(payload: dict) -> tuple[dict, dict, int | None]:
    """Split a cronjob {meta, body} envelope; fall back to bare body for direct UI calls."""
    if isinstance(payload.get("meta"), dict) and "body" in payload:
        meta = payload["meta"]
        body = payload["body"] if isinstance(payload["body"], dict) else {}
        run_id_raw = meta.get("run_id")
        cronjob_run_id = int(run_id_raw) if run_id_raw is not None else None
        return meta, body, cronjob_run_id
    return {}, payload, None


@router.post("/sample-runs", status_code=202)
async def create_sample_run(payload: dict, request: Request):
    """Create an async sample run. Returns immediately with a sample_run_id.

    Accepts both direct UI requests and cronjob {meta, body} envelopes. Duplicate
    concurrent submissions (same logical identity) are rejected with 409 unless
    ``force`` is set.
    """
    runtime = request.app.state.runtime
    if runtime.discovery_orchestrator is None:
        return JSONResponse(status_code=503, content={"error": "discovery orchestrator not configured"})
    _meta, body, cronjob_run_id = _parse_cronjob_envelope(payload)
    try:
        sample_req = SampleRunRequest(**body)
    except Exception as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    sample_run_id = str(uuid4())
    identity_key = sample_identity_key(
        sample_req.sample_size,
        sample_req.report_types,
        sample_req.published_from,
        sample_req.published_to,
        sample_req.sample_seed,
    )

    if not sample_req.force and runtime.sample_task_registry.is_active(identity_key):
        active = next(
            (h for h in runtime.sample_task_registry.active_handles() if h.identity_key == identity_key),
            None,
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_active_run",
                "existing_sample_run_id": active.run_id if active else None,
            },
        )

    await runtime.phoenixa.create_sample_run(
        sample_run_id,
        body,
        cronjob_run_id=cronjob_run_id,
        total=0,
        status="PENDING",
    )

    discovery = runtime.discovery_orchestrator
    cronjob_run_id_final = cronjob_run_id

    async def _setup_and_run() -> None:
        await discovery.run_sample(
            sample_run_id, sample_req, cronjob_run_id=cronjob_run_id_final
        )

    ok, existing = await runtime.sample_task_registry.try_register(
        identity_key, sample_run_id, cronjob_run_id, _setup_and_run
    )
    if not ok:
        await runtime.phoenixa.update_sample_run_status(
            sample_run_id, "FAILED", error_code="DUPLICATE_ACTIVE_RUN",
            error_message=f"another run is active: {existing}",
        )
        return JSONResponse(
            status_code=409,
            content={"error": "duplicate_active_run", "existing_sample_run_id": existing},
        )
    return {"sample_run_id": sample_run_id, "accepted": True, "cronjob_run_id": cronjob_run_id}


@router.get("/sample-runs")
async def list_sample_runs(request: Request, status: str = ""):
    """List sample runs (recent first) for the run selector on the extractions page."""
    items = await request.app.state.runtime.phoenixa.list_sample_runs(status=status)
    return {"data": items}


@router.get("/sample-runs/{run_id}")
async def get_sample_run(run_id: str, request: Request):
    return await request.app.state.runtime.phoenixa.get_sample_run(run_id)


@router.get("/sample-runs/{run_id}/category-results")
async def list_category_results(run_id: str, request: Request):
    items = await request.app.state.runtime.phoenixa.list_sample_category_results(run_id)
    return {"data": items}


@router.get("/sample-runs/{run_id}/category-results/{report_type}")
async def get_category_result(run_id: str, report_type: str, request: Request):
    return await request.app.state.runtime.phoenixa.get_sample_category_result(run_id, report_type)


@router.put("/sample-runs/{run_id}/category-results/{report_type}/field-summary")
async def update_field_summary(
    run_id: str, report_type: str, payload: dict, request: Request
):
    field_summary = payload.get("field_summary")
    if not isinstance(field_summary, dict):
        return JSONResponse(status_code=422, content={"error": "field_summary must be an object"})
    await request.app.state.runtime.phoenixa.update_sample_field_summary(
        run_id, report_type, field_summary
    )
    return {"updated": True}


@router.get("/sample-runs/{run_id}/document-results")
async def list_document_results(run_id: str, request: Request):
    items = await request.app.state.runtime.phoenixa.list_sample_document_results(run_id)
    return {"data": items}

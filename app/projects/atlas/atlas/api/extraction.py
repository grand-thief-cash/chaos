"""Extraction trigger & query endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from atlas.connectors import phoenixa_client
from atlas.services.llm_extractor import extract_from_chunk
from atlas.services.graph_builder import build_graph_from_extraction

router = APIRouter()


class TriggerRequest(BaseModel):
    doc_id: str
    chunk_texts: list[str] = []  # If empty, will be looked up
    model: str | None = None


class TriggerResponse(BaseModel):
    doc_id: str
    chunks_processed: int
    chunks_failed: int
    total_cost: float


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_extraction(req: TriggerRequest):
    """Trigger LLM extraction for a document's chunks and build graph."""
    chunks_ok = 0
    chunks_fail = 0
    total_cost = 0.0

    for i, text in enumerate(req.chunk_texts):
        result, raw = await extract_from_chunk(
            text, doc_id=req.doc_id, chunk_index=i, model=req.model,
        )
        total_cost += raw.get("cost", 0.0)

        if result is not None:
            # Store extraction in phoenixA
            try:
                ext_resp = await phoenixa_client.create_extraction({
                    "doc_id": req.doc_id,
                    "chunk_index": i,
                    "prompt_version": "v5",
                    "llm_model": raw.get("model", ""),
                    "graph_json": raw.get("parsed", {}),
                    "input_tokens": raw.get("input_tokens", 0),
                    "output_tokens": raw.get("output_tokens", 0),
                    "cost_usd": raw.get("cost", 0.0),
                    "status": "completed",
                })
                extraction_id = ext_resp.get("id", 0)
            except Exception:
                extraction_id = 0

            # Build graph
            await build_graph_from_extraction(result, extraction_id=extraction_id)
            chunks_ok += 1
        else:
            chunks_fail += 1
            try:
                await phoenixa_client.create_extraction({
                    "doc_id": req.doc_id,
                    "chunk_index": i,
                    "prompt_version": "v5",
                    "llm_model": raw.get("model", ""),
                    "graph_json": {},
                    "input_tokens": raw.get("input_tokens", 0),
                    "output_tokens": raw.get("output_tokens", 0),
                    "cost_usd": raw.get("cost", 0.0),
                    "status": "failed",
                })
            except Exception:
                pass

    # Mark document as processed
    try:
        await phoenixa_client.update_document(req.doc_id, {"processed": True})
    except Exception:
        pass

    return TriggerResponse(
        doc_id=req.doc_id,
        chunks_processed=chunks_ok,
        chunks_failed=chunks_fail,
        total_cost=total_cost,
    )


@router.get("")
async def list_extractions(
    doc_id: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List extraction results from phoenixA."""
    data = await phoenixa_client.list_extractions(
        doc_id=doc_id, status=status, limit=limit, offset=offset,
    )
    return {"extractions": data, "total": len(data)}


@router.get("/{ext_id}")
async def get_extraction(ext_id: int):
    """Get a single extraction result."""
    data = await phoenixa_client.get_extraction(ext_id)
    if data is None:
        return {"error": "Extraction not found"}
    return data


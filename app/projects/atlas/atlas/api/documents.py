"""Document upload & extraction endpoints."""
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel

from atlas.services.ingestion import ingest_document
from atlas.services.llm_extractor import extract_document_chunks
from atlas.services.graph_service import ingest_extraction_result

router = APIRouter()

# In-memory doc store (replace with MySQL in production)
_doc_store: dict[str, dict] = {}
_chunk_store: dict[str, list[str]] = {}


class UploadResponse(BaseModel):
    doc_id: str
    title: str
    chunk_count: int
    status: str


class ExtractResponse(BaseModel):
    doc_id: str
    chunks_processed: int
    nodes_created: int
    edges_created: int
    total_cost: float


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    source_type: str = Form("unknown"),
    company_name: str = Form(""),
    source_url: str = Form(""),
):
    """Upload a document (PDF/HTML/text) for processing."""
    data = await file.read()
    meta, chunks = ingest_document(
        filename=file.filename or "unknown",
        data=data,
        source_type=source_type,
        company_name=company_name,
        source_url=source_url,
    )
    _doc_store[meta.doc_id] = meta.model_dump()
    _chunk_store[meta.doc_id] = chunks
    return UploadResponse(
        doc_id=meta.doc_id,
        title=meta.title,
        chunk_count=meta.chunk_count,
        status=meta.status.value,
    )


@router.post("/{doc_id}/extract", response_model=ExtractResponse)
async def extract_document(doc_id: str):
    """Trigger LLM extraction for a previously uploaded document."""
    chunks = _chunk_store.get(doc_id)
    if not chunks:
        return ExtractResponse(doc_id=doc_id, chunks_processed=0,
                               nodes_created=0, edges_created=0, total_cost=0)

    results = await extract_document_chunks(chunks, doc_id=doc_id)

    total_nodes = 0
    total_edges = 0
    total_cost = 0.0
    chunks_ok = 0

    for result, raw in results:
        total_cost += raw.get("cost", 0.0)
        if result is not None:
            counts = ingest_extraction_result(result)
            total_nodes += counts["nodes"]
            total_edges += counts["edges"]
            chunks_ok += 1

    return ExtractResponse(
        doc_id=doc_id,
        chunks_processed=chunks_ok,
        nodes_created=total_nodes,
        edges_created=total_edges,
        total_cost=total_cost,
    )


@router.post("/batch-extract")
async def batch_extract(background_tasks: BackgroundTasks):
    """Trigger extraction for all pending documents (background task)."""
    pending = [
        doc_id for doc_id, meta in _doc_store.items()
        if meta.get("status") == "pending"
    ]
    background_tasks.add_task(_batch_extract_worker, pending)
    return {"message": f"Batch extraction started for {len(pending)} documents", "doc_ids": pending}


async def _batch_extract_worker(doc_ids: list[str]):
    for doc_id in doc_ids:
        try:
            await extract_document(doc_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed to extract doc %s: %s", doc_id, e)


@router.get("")
async def list_documents(status: str | None = None):
    """List all documents, optionally filtered by status."""
    docs = list(_doc_store.values())
    if status:
        docs = [d for d in docs if d.get("status") == status]
    return {"documents": docs, "total": len(docs)}


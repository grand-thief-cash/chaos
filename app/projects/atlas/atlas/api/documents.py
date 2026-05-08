"""Document upload & management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, Query
from pydantic import BaseModel

from atlas.connectors import phoenixa_client, minio_client
from atlas.services.ingestion import ingest_document

router = APIRouter()


class UploadResponse(BaseModel):
    doc_id: str
    title: str
    chunk_count: int
    status: str


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("manual"),
    company_name: str = Form(""),
    source_url: str = Form(""),
):
    """Upload a document (PDF/HTML/text) for processing."""
    data = await file.read()
    meta, chunks = ingest_document(
        filename=file.filename or "unknown",
        data=data,
        source_type=doc_type,
        company_name=company_name,
        source_url=source_url,
    )

    # Upload raw file to MinIO
    file_path = minio_client.upload_document(
        data=data,
        doc_id=meta.doc_id,
        filename=file.filename or "unknown",
        doc_type=doc_type,
    )

    # Determine source_type classification
    source_type = "event_triggering" if doc_type in ("news", "policy", "announcement") else "graph_building"

    # Register in phoenixA
    try:
        await phoenixa_client.create_document({
            "doc_id": meta.doc_id,
            "title": meta.title,
            "doc_type": doc_type,
            "source_type": source_type,
            "company": company_name,
            "file_path": file_path,
            "content_hash": meta.content_hash,
            "processed": False,
        })
    except Exception:
        pass  # Non-fatal: document is still accessible locally

    return UploadResponse(
        doc_id=meta.doc_id,
        title=meta.title,
        chunk_count=meta.chunk_count,
        status="uploaded",
    )


@router.post("/{doc_id}/extract")
async def extract_document(doc_id: str):
    """Trigger LLM extraction for a previously uploaded document."""
    from atlas.services.llm_extractor import extract_document_chunks
    from atlas.services.graph_builder import build_graph_from_extraction

    # Get document chunks from local storage or re-parse
    doc = await phoenixa_client.get_document(doc_id)
    if not doc:
        return {"error": "Document not found", "doc_id": doc_id}

    # Try to get the file from MinIO and re-parse
    file_path = doc.get("file_path", "")
    file_data = minio_client.download_document(file_path) if file_path else None

    if file_data is None:
        return {"error": "Document file not found in storage", "doc_id": doc_id}

    from atlas.services.ingestion import extract_text, split_into_chunks
    from atlas.core.config import get_config
    cfg = get_config()["document"]

    filename = file_path.split("/")[-1] if "/" in file_path else file_path
    text = extract_text(filename, file_data)
    chunks = split_into_chunks(text, cfg.get("chunk_max_chars", 3000), cfg.get("chunk_overlap_chars", 200))

    results = await extract_document_chunks(chunks, doc_id=doc_id)

    total_nodes = 0
    total_edges = 0
    total_cost = 0.0
    chunks_ok = 0

    for result, raw in results:
        total_cost += raw.get("cost", 0.0)
        if result is not None:
            counts = await build_graph_from_extraction(result)
            total_nodes += counts["nodes_created"]
            total_edges += counts["edges_created"]
            chunks_ok += 1

    # Mark as processed
    try:
        await phoenixa_client.update_document(doc_id, {"processed": True})
    except Exception:
        pass

    return {
        "doc_id": doc_id,
        "chunks_processed": chunks_ok,
        "nodes_created": total_nodes,
        "edges_created": total_edges,
        "total_cost": total_cost,
    }


@router.get("")
async def list_documents(
    doc_type: str = "",
    source_type: str = "",
    status: str = "",
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """List all documents from phoenixA."""
    processed = None
    if status == "completed":
        processed = True
    elif status == "pending":
        processed = False

    docs = await phoenixa_client.list_documents(
        doc_type=doc_type,
        source_type=source_type,
        processed=processed,
        limit=limit,
        offset=offset,
    )
    return {"documents": docs, "total": len(docs)}


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get a single document."""
    doc = await phoenixa_client.get_document(doc_id)
    if not doc:
        return {"error": "Document not found", "doc_id": doc_id}
    return doc


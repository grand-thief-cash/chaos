"""Web clip endpoint — browser bookmarklet submission."""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from atlas.connectors import phoenixa_client, minio_client

router = APIRouter()


class WebClipRequest(BaseModel):
    title: str = ""
    url: str = ""
    content: str = ""
    doc_type: str = "news"  # news|research|policy|announcement


class WebClipResponse(BaseModel):
    doc_id: str
    status: str
    message: str


@router.post("/web-clip", response_model=WebClipResponse)
async def submit_web_clip(req: WebClipRequest):
    """Accept content from browser bookmarklet and queue for processing."""
    if not req.content and not req.title:
        return WebClipResponse(doc_id="", status="error", message="No content provided")

    doc_id = uuid.uuid4().hex[:16]
    content_bytes = req.content.encode("utf-8")
    content_hash = hashlib.sha256(content_bytes).hexdigest()

    # Check for duplicate content
    existing = await phoenixa_client.list_documents(limit=1)
    # Simple hash-based dedup: check via content_hash in query would require filter support
    # For now, just proceed

    # Upload to MinIO
    filename = f"{req.title[:50] or 'web_clip'}.txt".replace("/", "_").replace("\\", "_")
    file_path = minio_client.upload_document(
        data=content_bytes,
        doc_id=doc_id,
        filename=filename,
        doc_type=req.doc_type,
    )

    # Determine source_type based on doc_type
    source_type = "event_triggering" if req.doc_type in ("news", "policy", "announcement") else "graph_building"

    # Register in phoenixA
    await phoenixa_client.create_document({
        "doc_id": doc_id,
        "title": req.title or filename,
        "doc_type": req.doc_type,
        "source_type": source_type,
        "file_path": file_path,
        "content_hash": content_hash,
        "processed": False,
    })

    return WebClipResponse(
        doc_id=doc_id,
        status="queued",
        message=f"Document submitted for processing (type={req.doc_type})",
    )


"""Document ingestion — parse PDF / HTML / plain text and split into chunks."""
from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Optional

from atlas.core.config import get_config
from atlas.models.document import DocumentMeta, DocStatus

logger = logging.getLogger(__name__)


def _storage_dir() -> Path:
    cfg = get_config()
    d = Path(cfg["document"]["storage_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def compute_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_text_from_pdf(data: bytes) -> str:
    """Extract full text from PDF bytes using PyMuPDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=data, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n\n".join(pages)


def extract_text_from_html(data: bytes) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(data, "html.parser")
    # Remove script / style tags
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(data)
    elif ext in (".html", ".htm"):
        return extract_text_from_html(data)
    else:
        # Treat as plain text
        return data.decode("utf-8", errors="replace")


# ── Chunking ───────────────────────────────────────────────────────────────────

def split_into_chunks(text: str, max_chars: int = 3000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks by paragraph boundaries.

    Prefers splitting at paragraph breaks (double newline) to preserve context.
    Falls back to hard split if a single paragraph exceeds *max_chars*.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            # Handle oversized paragraph
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars - overlap):
                    chunks.append(para[i : i + max_chars])
            else:
                # Start new chunk with overlap from previous
                if chunks and overlap > 0:
                    prev_tail = chunks[-1][-overlap:]
                    current = prev_tail + "\n\n" + para
                else:
                    current = para
                continue
            current = ""

    if current:
        chunks.append(current)

    return chunks


# ── High-level ingest ─────────────────────────────────────────────────────────

def ingest_document(
    filename: str,
    data: bytes,
    source_type: str = "unknown",
    company_name: str = "",
    source_url: str = "",
) -> tuple[DocumentMeta, list[str]]:
    """Parse document and return (metadata, list_of_text_chunks).

    The caller is responsible for persisting metadata and triggering extraction.
    """
    cfg = get_config()["document"]
    content_hash = compute_hash(data)
    doc_id = uuid.uuid4().hex[:16]

    # Save raw file
    raw_path = _storage_dir() / f"{doc_id}_{filename}"
    raw_path.write_bytes(data)

    text = extract_text(filename, data)
    chunks = split_into_chunks(
        text,
        max_chars=cfg.get("chunk_max_chars", 3000),
        overlap=cfg.get("chunk_overlap_chars", 200),
    )

    meta = DocumentMeta(
        doc_id=doc_id,
        title=filename,
        source_type=source_type,
        source_url=source_url,
        company_name=company_name,
        content_hash=content_hash,
        status=DocStatus.PENDING,
        chunk_count=len(chunks),
    )

    logger.info(
        "Ingested document %s → %d chunks (hash=%s)",
        filename, len(chunks), content_hash[:12],
    )
    return meta, chunks


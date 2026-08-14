from __future__ import annotations

import asyncio
from typing import Protocol

import httpx

from atlas.knowledge_production.pdf_preprocessor.text_extractor import PDFTextPage


class LayoutParserSidecar(Protocol):
    async def extract_pages(self, pdf: bytes, *, filename: str) -> list[PDFTextPage]: ...


class HTTPLayoutParserSidecar:
    """Small adapter for an isolated Docling/PP-Structure deployment.

    Expected response: ``{"pages":[{"page_number":1,"text":"..."}]}``.
    Heavy parser packages and model weights stay outside the Atlas venv.
    """

    def __init__(self, base_url: str, *, timeout_seconds: float = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def extract_pages(self, pdf: bytes, *, filename: str) -> list[PDFTextPage]:
        response = await self._client.post(
            f"{self.base_url}/v1/parse-pdf",
            files={"file": (filename, pdf, "application/pdf")},
        )
        response.raise_for_status()
        body = response.json()
        pages = [
            PDFTextPage(int(item["page_number"]), str(item.get("text") or "").strip())
            for item in body.get("pages") or []
        ]
        if not pages or not any(page.text for page in pages):
            raise ValueError("layout sidecar returned no usable page text")
        return pages

    async def close(self) -> None:
        await self._client.aclose()


class RapidOCRLayoutParser:
    """Lazy, CPU-only OCR fallback for resource-constrained deployments.

    RapidOCR and PyMuPDF are imported inside the worker thread so the normal
    pdfplumber path pays no model-memory or import cost. Calls are serialized:
    correctness matters more than overloading a small CPU host. The same
    parser can serve development Sampling and production full extraction.
    """

    def __init__(self, *, dpi: int = 160, maximum_pages: int = 12) -> None:
        self.dpi = dpi
        self.maximum_pages = maximum_pages
        self._lock = asyncio.Lock()

    async def extract_pages(self, pdf: bytes, *, filename: str) -> list[PDFTextPage]:
        async with self._lock:
            return await asyncio.to_thread(self._extract_sync, pdf)

    def _extract_sync(self, pdf: bytes) -> list[PDFTextPage]:
        import fitz
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR

        document = fitz.open(stream=pdf, filetype="pdf")
        try:
            if len(document) > self.maximum_pages:
                indexes = _representative_page_indexes(
                    len(document), self.maximum_pages
                )
            else:
                indexes = list(range(len(document)))
            engine = RapidOCR()
            scale = self.dpi / 72.0
            pages: list[PDFTextPage] = []
            for index in indexes:
                pixmap = document[index].get_pixmap(
                    matrix=fitz.Matrix(scale, scale),
                    colorspace=fitz.csRGB,
                    alpha=False,
                )
                image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                result, _ = engine(image)
                text = "\n".join(
                    str(item[1]).strip()
                    for item in (result or [])
                    if len(item) > 1 and str(item[1]).strip()
                )
                pages.append(PDFTextPage(index + 1, text))
            return pages
        finally:
            document.close()


def _representative_page_indexes(page_count: int, maximum_pages: int) -> list[int]:
    if page_count <= 0 or maximum_pages <= 0:
        return []
    if maximum_pages == 1:
        return [0]
    if page_count <= maximum_pages:
        return list(range(page_count))
    # Include both ends and evenly-spaced middle pages without scanning an
    # arbitrarily long document in development.
    indexes = {
        round(position * (page_count - 1) / (maximum_pages - 1))
        for position in range(maximum_pages)
    }
    return sorted(indexes)

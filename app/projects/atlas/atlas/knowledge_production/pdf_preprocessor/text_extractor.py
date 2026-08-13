from __future__ import annotations

import math
import re
from dataclasses import dataclass
from io import BytesIO

from atlas.core.errors import ModelPDFUnreadableError, PDFTextExtractionError


_BOILERPLATE_RE = re.compile(
    r"免责声明|分析师声明|投资评级说明|行业评级说明|证券投资咨询业务资格|"
    r"本报告仅供|未经(?:书面)?许可|版权所有|执业证书|联系地址|邮政编码"
)
_RESEARCH_SIGNAL_RE = re.compile(
    r"产业链|上游|下游|产品|技术|客户|供应商|竞争|市场|行业|政策|供需|"
    r"产能|收入|利润|增长|预测|风险提示|投资要点|核心观点"
)


@dataclass(frozen=True, slots=True)
class PDFTextPage:
    number: int
    text: str

    def render(self) -> str:
        return (
            f'<atlas_pdf_page number="{self.number}">\n'
            f"{self.text}\n"
            "</atlas_pdf_page>"
        )


@dataclass(frozen=True, slots=True)
class PDFTextChunk:
    pages: tuple[PDFTextPage, ...]
    index: int
    total: int
    coverage_truncated: bool = False

    @property
    def text(self) -> str:
        return "\n".join(page.render() for page in self.pages)

    @property
    def page_numbers(self) -> list[int]:
        return [page.number for page in self.pages]


@dataclass(frozen=True, slots=True)
class PDFTextQuality:
    page_count: int
    empty_page_count: int
    low_text_page_count: int
    visible_characters: int
    research_signal_count: int
    suspicious_axis_page_count: int
    escalation_reasons: tuple[str, ...] = ()

    @property
    def requires_layout_fallback(self) -> bool:
        return bool(self.escalation_reasons)

    @property
    def recommended_parser(self) -> str:
        if "IMAGE_ONLY_OR_EMPTY_TEXT_LAYER" in self.escalation_reasons:
            return "pp-structure-v3-ocr"
        return "docling-standard"


def extract_pdf_pages(
    pdf: bytes, *, layout: bool = False, allow_empty: bool = False
) -> list[PDFTextPage]:
    """Extract page text once while preserving authoritative PDF page ids."""
    try:
        import pdfplumber

        pages: list[PDFTextPage] = []
        with pdfplumber.open(BytesIO(pdf)) as document:
            for page_number, page in enumerate(document.pages, start=1):
                text = page.extract_text(layout=True) if layout else page.extract_text()
                pages.append(PDFTextPage(page_number, (text or "").strip()))
    except Exception as exc:
        raise PDFTextExtractionError(str(exc)) from exc
    if not allow_empty and not any(page.text for page in pages):
        raise ModelPDFUnreadableError(
            "pdfplumber extracted no text; scanned/image-only PDF requires OCR fallback"
        )
    return pages


def extract_pdf_pages_for_sampling(pdf: bytes) -> list[PDFTextPage]:
    """Sampling variant that preserves empty pages for parser routing."""
    return extract_pdf_pages(pdf, allow_empty=True)


def render_pdf_pages(pages: list[PDFTextPage] | tuple[PDFTextPage, ...]) -> str:
    return "\n".join(page.render() for page in pages)


_AXIS_LABEL_RE = re.compile(r"(?<!\d)-?\d+(?:\.\d+)?%")


def assess_pdf_text_quality(pages: list[PDFTextPage]) -> PDFTextQuality:
    """Route only clearly bad text layers to an optional layout/OCR sidecar.

    This is intentionally conservative: chart-heavy research PDFs often still
    contain enough narrative text for sampling. A few percentage labels alone
    must not trigger an expensive second parser.
    """
    page_count = len(pages)
    empty_pages = sum(not "".join(page.text.split()) for page in pages)
    low_text_pages = sum(
        1 for page in pages if len("".join(page.text.split())) < 80
    )
    visible_characters = sum(len("".join(page.text.split())) for page in pages)
    research_signal_count = sum(len(_RESEARCH_SIGNAL_RE.findall(page.text)) for page in pages)
    suspicious_axis_pages = 0
    for page in pages:
        compact = "".join(page.text.split())
        axis_labels = len(_AXIS_LABEL_RE.findall(page.text))
        page_research_signals = len(_RESEARCH_SIGNAL_RE.findall(page.text))
        if axis_labels >= 6 and page_research_signals == 0 and len(compact) < 600:
            suspicious_axis_pages += 1

    reasons: list[str] = []
    if page_count and empty_pages / page_count >= 0.8:
        reasons.append("IMAGE_ONLY_OR_EMPTY_TEXT_LAYER")
    elif page_count and low_text_pages / page_count >= 0.7 and visible_characters < 1200:
        reasons.append("TEXT_LAYER_TOO_SPARSE")
    if (
        page_count
        and suspicious_axis_pages / page_count >= 0.5
        and research_signal_count < 3
    ):
        reasons.append("CHART_LABEL_DOMINATED_TEXT_LAYER")
    return PDFTextQuality(
        page_count=page_count,
        empty_page_count=empty_pages,
        low_text_page_count=low_text_pages,
        visible_characters=visible_characters,
        research_signal_count=research_signal_count,
        suspicious_axis_page_count=suspicious_axis_pages,
        escalation_reasons=tuple(reasons),
    )


def estimate_tokens(text: str) -> int:
    """Conservative mixed Chinese/English estimate without a tokenizer dependency."""
    return max(1, math.ceil(len(text) / 1.45))


def chunk_pdf_pages(
    pages: list[PDFTextPage],
    *,
    maximum_chunk_tokens: int,
    maximum_chunks: int = 6,
) -> list[PDFTextChunk]:
    """Build page-boundary chunks and make any coverage loss explicit."""
    if maximum_chunk_tokens < 256:
        raise ValueError("maximum_chunk_tokens must be at least 256")
    if maximum_chunks < 1:
        raise ValueError("maximum_chunks must be positive")

    groups: list[list[PDFTextPage]] = []
    current: list[PDFTextPage] = []
    current_tokens = 0
    maximum_chars = int(maximum_chunk_tokens * 1.45)
    for page in pages:
        page_tokens = estimate_tokens(page.render())
        fitted_page = page
        if page_tokens > maximum_chunk_tokens:
            fitted_page = PDFTextPage(
                page.number,
                page.text[:maximum_chars] + "\n[ATLAS_PAGE_TEXT_TRUNCATED]",
            )
            page_tokens = estimate_tokens(fitted_page.render())
        if current and current_tokens + page_tokens > maximum_chunk_tokens:
            groups.append(current)
            current = []
            current_tokens = 0
        current.append(fitted_page)
        current_tokens += page_tokens
    if current:
        groups.append(current)

    coverage_truncated = len(groups) > maximum_chunks
    if coverage_truncated:
        selected = _select_representative_groups(groups, maximum_chunks)
    else:
        selected = groups
    total = len(selected)
    return [
        PDFTextChunk(
            pages=tuple(group),
            index=index,
            total=total,
            coverage_truncated=coverage_truncated,
        )
        for index, group in enumerate(selected, start=1)
    ]


def _select_representative_groups(
    groups: list[list[PDFTextPage]], maximum_chunks: int
) -> list[list[PDFTextPage]]:
    """Cover the document while avoiding expensive disclaimer-only tail chunks."""
    if maximum_chunks == 1:
        return [groups[0]]

    selected_indexes = [0]
    remaining_count = len(groups) - 1
    bucket_count = maximum_chunks - 1
    for bucket in range(bucket_count):
        start = 1 + (bucket * remaining_count // bucket_count)
        end = 1 + ((bucket + 1) * remaining_count // bucket_count)
        target = round((bucket + 1) * (len(groups) - 1) / bucket_count)
        candidates = range(start, max(start + 1, end))
        chosen = max(
            candidates,
            key=lambda index: (
                _research_group_score(groups[index]),
                -abs(index - target),
            ),
        )
        selected_indexes.append(chosen)
    return [groups[index] for index in sorted(set(selected_indexes))]


def _research_group_score(group: list[PDFTextPage]) -> int:
    text = "\n".join(page.text for page in group)
    visible_characters = len("".join(text.split()))
    research_signals = len(_RESEARCH_SIGNAL_RE.findall(text))
    boilerplate_signals = len(_BOILERPLATE_RE.findall(text))
    return (
        min(visible_characters, 5000)
        + min(research_signals, 24) * 120
        - min(boilerplate_signals, 12) * 1200
    )

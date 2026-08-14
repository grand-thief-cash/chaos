from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Callable

from atlas.core.errors import ModelPDFUnreadableError
from atlas.core.harness_events import HarnessEventRegistry
from atlas.knowledge_production.pdf_preprocessor.layout_sidecar import (
    LayoutParserSidecar,
)
from atlas.knowledge_production.pdf_preprocessor.text_extractor import (
    PDFTextPage,
    PDFTextQuality,
    assess_pdf_text_quality,
    extract_pdf_pages,
    render_pdf_pages,
)


@dataclass(frozen=True, slots=True)
class DocumentParseResult:
    pages: tuple[PDFTextPage, ...]
    parser: str
    source_page_count: int
    coverage_truncated: bool
    primary_quality: PDFTextQuality
    final_quality: PDFTextQuality
    quality_issues: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        coverage = "partial" if self.coverage_truncated else "complete"
        header = (
            f'<atlas_document_parse parser="{self.parser}" '
            f'source_page_count="{self.source_page_count}" '
            f'coverage="{coverage}" />'
        )
        return header + "\n" + render_pdf_pages(self.pages)


class DocumentParserHarness:
    """Quality-gated PDF parser shared by Sampling and Production.

    pdfplumber is the inexpensive primary parser. A configured layout/OCR
    parser is invoked only when deterministic quality signals request it, and
    its result replaces the primary text only when it measurably improves the
    usable text or research signals.
    """

    def __init__(
        self,
        fallback: LayoutParserSidecar | None = None,
        *,
        events: HarnessEventRegistry | None = None,
        primary_extractor: Callable[..., list[PDFTextPage]] = extract_pdf_pages,
    ) -> None:
        self.fallback = fallback
        self.events = events
        self.primary_extractor = primary_extractor

    @property
    def signature(self) -> str:
        if self.fallback is None:
            return "pdfplumber+no-fallback"
        name = type(self.fallback).__name__
        dpi = getattr(self.fallback, "dpi", "na")
        maximum_pages = getattr(self.fallback, "maximum_pages", "na")
        return f"pdfplumber+{name}:dpi={dpi}:max_pages={maximum_pages}"

    async def parse(
        self,
        pdf: bytes,
        *,
        filename: str,
        allow_empty: bool = False,
    ) -> DocumentParseResult:
        self._emit("PRIMARY_PARSER_STARTED", "开始读取 PDF 文本层", parser="pdfplumber")
        primary_pages = await asyncio.to_thread(self._extract_primary, pdf)
        primary_quality = assess_pdf_text_quality(primary_pages)
        self._emit(
            "PRIMARY_PARSER_COMPLETED",
            "PDF 文本层质量评估完成",
            parser="pdfplumber",
            details=_quality_details(primary_quality),
        )
        pages = primary_pages
        final_quality = primary_quality
        parser = "pdfplumber"
        issues = [
            f"PARSER_ESCALATION_RECOMMENDED:{reason}"
            for reason in primary_quality.escalation_reasons
        ]

        if primary_quality.requires_layout_fallback:
            self._emit(
                "PARSER_ESCALATION_REQUESTED",
                "文本质量门请求 layout/OCR fallback",
                level="WARNING",
                parser="pdfplumber",
                details={"reasons": primary_quality.escalation_reasons},
            )
            if self.fallback is None:
                issues.append("PARSER_FALLBACK_NOT_CONFIGURED")
                self._emit(
                    "PARSER_FALLBACK_UNAVAILABLE",
                    "未配置 layout/OCR fallback",
                    level="WARNING",
                )
            else:
                fallback_name = type(self.fallback).__name__
                self._emit(
                    "PARSER_FALLBACK_STARTED",
                    "开始执行 layout/OCR fallback",
                    parser=fallback_name,
                )
                try:
                    fallback_pages = await self.fallback.extract_pages(
                        pdf, filename=filename
                    )
                    fallback_quality = assess_pdf_text_quality(fallback_pages)
                    if _is_improvement(primary_quality, fallback_quality):
                        pages = fallback_pages
                        final_quality = fallback_quality
                        parser = fallback_name
                        issues.append("PARSER_FALLBACK_USED")
                        # Preserve the pre-Harness diagnostic consumed by existing
                        # Sampling result reviewers and historical tests.
                        issues.append("LAYOUT_SIDECAR_USED")
                        self._emit(
                            "PARSER_FALLBACK_ACCEPTED",
                            "fallback 提升了可用文本质量，已采用",
                            parser=fallback_name,
                            details=_quality_details(fallback_quality),
                        )
                    else:
                        issues.append("PARSER_FALLBACK_NO_IMPROVEMENT")
                        self._emit(
                            "PARSER_FALLBACK_REJECTED",
                            "fallback 未提升文本质量，保留 pdfplumber 结果",
                            level="WARNING",
                            parser=fallback_name,
                            details=_quality_details(fallback_quality),
                        )
                except Exception as exc:
                    issues.append("PARSER_FALLBACK_FAILED")
                    self._emit(
                        "PARSER_FALLBACK_FAILED",
                        "layout/OCR fallback 执行失败",
                        level="ERROR",
                        parser=fallback_name,
                        details={"error_type": type(exc).__name__, "reason": str(exc)},
                    )

        if not any(page.text for page in pages) and not allow_empty:
            raise ModelPDFUnreadableError(
                "document parser harness produced no usable page text"
            )
        result = DocumentParseResult(
            pages=tuple(pages),
            parser=parser,
            source_page_count=len(primary_pages),
            coverage_truncated=len(pages) < len(primary_pages),
            primary_quality=primary_quality,
            final_quality=final_quality,
            quality_issues=tuple(dict.fromkeys(issues)),
        )
        self._emit(
            "DOCUMENT_PARSE_COMPLETED",
            "Document Harness 已生成页级文本",
            parser=parser,
            details={
                **_quality_details(final_quality),
                "source_page_count": result.source_page_count,
                "selected_page_count": len(result.pages),
                "coverage_truncated": result.coverage_truncated,
            },
        )
        return result

    def _extract_primary(self, pdf: bytes) -> list[PDFTextPage]:
        """Keep compatibility with injected one-argument parser functions."""
        try:
            return self.primary_extractor(pdf, allow_empty=True)
        except TypeError as exc:
            if "allow_empty" not in str(exc):
                raise
            return self.primary_extractor(pdf)

    def _emit(self, event_type: str, message: str, **kwargs) -> None:
        if self.events is not None:
            self.events.emit(
                stage="document.parse",
                event_type=event_type,
                message=message,
                **kwargs,
            )


def _is_improvement(primary: PDFTextQuality, fallback: PDFTextQuality) -> bool:
    if primary.visible_characters == 0 and fallback.visible_characters > 0:
        return True
    return (
        fallback.research_signal_count > primary.research_signal_count
        or fallback.visible_characters > primary.visible_characters
    )


def _quality_details(quality: PDFTextQuality) -> dict:
    return {
        "page_count": quality.page_count,
        "empty_page_count": quality.empty_page_count,
        "low_text_page_count": quality.low_text_page_count,
        "visible_characters": quality.visible_characters,
        "research_signal_count": quality.research_signal_count,
        "suspicious_axis_page_count": quality.suspicious_axis_page_count,
        "escalation_reasons": quality.escalation_reasons,
    }

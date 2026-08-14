from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from atlas.core.clients import PDFLLMClient
from atlas.core.harness_events import HarnessEventRegistry
from atlas.knowledge_production.extractor.free_extraction_prompt import (
    FreeExtractionPromptBuilder,
)
from atlas.knowledge_production.pdf_preprocessor import (
    DocumentParserHarness,
    assess_pdf_text_quality,
    chunk_pdf_pages,
    extract_pdf_pages_for_sampling as extract_pdf_pages,
)
from atlas.models import Readability, ThinkingMode
from atlas.models.free_extraction import FreeExtractionResult

logger = logging.getLogger(__name__)

_META_RESPONSE_KEYS = {"status", "message", "error", "done", "ok", "result", "success"}
_SUBTYPE_KEYS = ("document_subtype", "文档子类型", "报告子类型", "研报类型", "报告类型")


class ModelDeclaredChunkUnreadableError(ValueError):
    """The model explicitly found no research content in this selected chunk."""


class FreeExtractionExtractor:
    """Produce model-authored document JSON, using map/merge for long PDFs."""

    def __init__(
        self,
        llm: PDFLLMClient,
        *,
        prompt_builder: FreeExtractionPromptBuilder | None = None,
        maximum_total_attempts: int = 2,
        thinking_mode: ThinkingMode | None = None,
        chunk_output_tokens: int = 1536,
        merge_output_tokens: int = 2560,
        maximum_chunks: int = 3,
        prompt_reserve_tokens: int = 2200,
        document_parser: DocumentParserHarness | None = None,
        layout_sidecar: Any | None = None,
        events: HarnessEventRegistry | None = None,
    ) -> None:
        self.llm = llm
        self.prompt_builder = prompt_builder or FreeExtractionPromptBuilder()
        self.maximum_total_attempts = maximum_total_attempts
        self.thinking_mode = thinking_mode
        self.chunk_output_tokens = chunk_output_tokens
        self.merge_output_tokens = merge_output_tokens
        self.maximum_chunks = maximum_chunks
        self.prompt_reserve_tokens = prompt_reserve_tokens
        if document_parser is not None and layout_sidecar is not None:
            raise ValueError("configure document_parser or layout_sidecar, not both")
        self.document_parser = document_parser or DocumentParserHarness(
            layout_sidecar,
            events=events,
            primary_extractor=extract_pdf_pages,
        )
        self.events = events

    async def extract(
        self,
        *,
        pdf: bytes,
        filename: str,
        document_id: str,
        title: str,
        report_type: str,
        report_profile: dict | None = None,
    ) -> tuple[FreeExtractionResult, int]:
        complete_text = getattr(self.llm, "complete_text", None)
        if callable(complete_text) and getattr(self.llm, "input_mode", "") == "TEXT_EXTRACTED":
            return await self._extract_text_chunks(
                pdf=pdf,
                filename=filename,
                document_id=document_id,
                title=title,
                report_type=report_type,
                report_profile=report_profile,
            )
        return await self._extract_whole_pdf(
            pdf=pdf,
            filename=filename,
            document_id=document_id,
            title=title,
            report_type=report_type,
            report_profile=report_profile,
        )

    async def _extract_text_chunks(
        self,
        *,
        pdf: bytes,
        filename: str,
        document_id: str,
        title: str,
        report_type: str,
        report_profile: dict | None,
    ) -> tuple[FreeExtractionResult, int]:
        parsed = await self.document_parser.parse(
            pdf, filename=filename, allow_empty=True
        )
        pages = list(parsed.pages)
        text_quality = parsed.final_quality
        parser_issues: list[str] = list(parsed.quality_issues)
        if not any(page.text for page in pages):
            return _unreadable_result(
                document_id,
                report_type,
                title,
                "PDF has no usable text layer; gated OCR sidecar is required",
                source_page_count=len(pages),
                quality_issues=[
                    f"PARSER_ESCALATION_RECOMMENDED:{reason}"
                    for reason in text_quality.escalation_reasons
                ],
            ), 0
        context_tokens = getattr(
            getattr(self.llm, "config", None), "context_window_tokens", 4096
        )
        chunk_budget = max(
            512,
            context_tokens - self.chunk_output_tokens - self.prompt_reserve_tokens,
        )
        chunks = chunk_pdf_pages(
            pages,
            maximum_chunk_tokens=chunk_budget,
            maximum_chunks=self.maximum_chunks,
        )
        self._emit(
            "CHUNK_PLAN_CREATED",
            f"文档已规划为 {len(chunks)} 个代表性页段",
            details={
                "chunk_count": len(chunks),
                "page_count": len(pages),
                "chunk_budget_tokens": chunk_budget,
                "coverage_truncated": any(chunk.coverage_truncated for chunk in chunks),
            },
        )
        extracted_chunks: list[tuple[Any, dict[str, Any]]] = []
        attempts = 0
        errors: list[str] = []
        recovered_chunk_indexes: list[int] = []
        for chunk in chunks:
            self._emit(
                "CHUNK_EXTRACTION_STARTED",
                f"开始理解页段 {chunk.index}/{chunk.total}",
                details={"chunk_index": chunk.index, "page_numbers": chunk.page_numbers},
            )
            prompt = self.prompt_builder.build(
                document_id=document_id,
                title=title,
                report_type=report_type,
                report_profile=report_profile,
            )
            prompt += (
                f"\n\n当前输入是同一文档的第 {chunk.index}/{chunk.total} 个页段，"
                f"包含 PDF 页 {chunk.page_numbers}。请充分理解本页段，按内容自由组织 JSON；"
                "不要猜测未提供页段的内容。"
            )
            content, used_attempts, error, recovered = await self._extract_one_text_chunk(
                prompt=prompt,
                extracted_text=chunk.text,
                filename=filename,
                document_id=document_id,
            )
            attempts += used_attempts
            if content is not None:
                extracted_chunks.append((chunk, content))
                self._emit(
                    "CHUNK_EXTRACTION_ACCEPTED",
                    f"页段 {chunk.index}/{chunk.total} 已产生有效自由 JSON",
                    details={"chunk_index": chunk.index, "attempts": used_attempts},
                )
            if recovered:
                recovered_chunk_indexes.append(chunk.index)
            if error:
                errors.append(f"chunk {chunk.index}: {error}")

        issues: list[str] = parser_issues + [
            f"PARSER_ESCALATION_RECOMMENDED:{reason}"
            for reason in text_quality.escalation_reasons
        ]
        if any(chunk.coverage_truncated for chunk in chunks):
            issues.append("TEXT_COVERAGE_TRUNCATED_BY_CHUNK_BUDGET")
        if errors:
            issues.append("PARTIAL_CHUNK_FAILURE")
        if recovered_chunk_indexes:
            issues.append("TRUNCATED_JSON_RECOVERED")
        if not extracted_chunks:
            _append_provider_issues(self.llm, issues)
            return _unreadable_result(
                document_id,
                report_type,
                title,
                "; ".join(errors) or "no chunk produced meaningful JSON",
                source_page_count=len(pages),
                quality_issues=issues,
            ), attempts

        if len(extracted_chunks) == 1:
            content = extracted_chunks[0][1]
        else:
            self._emit(
                "DOCUMENT_MERGE_STARTED",
                "开始合并各页段自由 JSON",
                details={"chunk_count": len(extracted_chunks)},
            )
            content, merge_attempts, merge_error = await self._merge_document_content(
                document_id=document_id,
                title=title,
                report_type=report_type,
                filename=filename,
                extracted_chunks=extracted_chunks,
            )
            attempts += merge_attempts
            if merge_error:
                issues.append("DOCUMENT_MERGE_FALLBACK")
                errors.append(f"merge: {merge_error}")
                self._emit(
                    "DOCUMENT_MERGE_FALLBACK",
                    "模型合并失败，保留可审阅的分段结果",
                    level="WARNING",
                    details={"reason": merge_error},
                )
            else:
                self._emit(
                    "DOCUMENT_MERGE_ACCEPTED",
                    "各页段已合并为单文档自由 JSON",
                    details={"chunk_count": len(extracted_chunks)},
                )

        _append_provider_issues(self.llm, issues)

        covered_pages = sorted({
            page_number
            for chunk, _ in extracted_chunks
            for page_number in chunk.page_numbers
        })
        subtype_hint = (report_profile or {}).get("sampling_subtype")
        subtype = _find_subtype(content)
        if not subtype or subtype == "unknown":
            subtype = subtype_hint or "unknown"
        return FreeExtractionResult(
            document_id=document_id,
            report_type=report_type,
            observed_title=title,
            document_subtype=subtype,
            content=content,
            covered_page_numbers=covered_pages,
            source_page_count=len(pages),
            chunk_count=len(extracted_chunks),
            coverage_truncated=any(chunk.coverage_truncated for chunk in chunks),
            quality_issues=list(dict.fromkeys(issues)),
        ), attempts

    def _emit(self, event_type: str, message: str, **kwargs: Any) -> None:
        if self.events is not None:
            self.events.emit(
                stage="workflow.document_understanding",
                event_type=event_type,
                message=message,
                **kwargs,
            )

    async def _extract_one_text_chunk(
        self,
        *,
        prompt: str,
        extracted_text: str,
        filename: str,
        document_id: str,
    ) -> tuple[dict[str, Any] | None, int, str | None, bool]:
        last_error: str | None = None
        raw_excerpt = ""
        for attempt in range(1, self.maximum_total_attempts + 1):
            retry_prompt = prompt
            if last_error:
                retry_prompt += (
                    "\n\n上一次没有返回有效的文档内容 JSON："
                    f"{last_error}。请重新阅读本页段，只输出一个内容充分的 JSON object。"
                )
            try:
                call_kwargs = dict(
                    prompt=retry_prompt,
                    extracted_text=extracted_text,
                    filename=filename,
                    thinking_mode=self.thinking_mode,
                    max_tokens=self.chunk_output_tokens,
                    response_schema=None,
                )
                complete_validated = getattr(
                    self.llm, "complete_text_validated", None
                )
                if callable(complete_validated):
                    raw = await complete_validated(
                        validator=_parse_free_content_detailed,
                        **call_kwargs,
                    )
                else:
                    raw = await self.llm.complete_text(**call_kwargs)
                raw_excerpt = raw[:800]
                content, recovered = _parse_free_content_detailed(raw)
                if recovered:
                    logger.warning(
                        "recovered a complete JSON prefix from truncated model output "
                        "for %s (attempt %d/%d)",
                        document_id,
                        attempt,
                        self.maximum_total_attempts,
                    )
                return content, attempt, None, recovered
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "free document chunk failed (attempt %d/%d) for %s: %s | raw[:800]=%s",
                    attempt,
                    self.maximum_total_attempts,
                    document_id,
                    last_error,
                    raw_excerpt,
                )
                if isinstance(exc, ModelDeclaredChunkUnreadableError):
                    return None, attempt, last_error, False
        return None, self.maximum_total_attempts, last_error, False

    async def _merge_document_content(
        self,
        *,
        document_id: str,
        title: str,
        report_type: str,
        filename: str,
        extracted_chunks: list[tuple[Any, dict[str, Any]]],
    ) -> tuple[dict[str, Any], int, str | None]:
        prompt = self.prompt_builder.build_merge(
            document_id=document_id,
            title=title,
            report_type=report_type,
            chunk_page_ranges=[chunk.page_numbers for chunk, _ in extracted_chunks],
        )
        merge_input = json.dumps(
            [
                {"pages": chunk.page_numbers, "content": content}
                for chunk, content in extracted_chunks
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            call_kwargs = dict(
                prompt=prompt,
                extracted_text=merge_input,
                filename=f"{filename}.chunk-results.json",
                thinking_mode=self.thinking_mode,
                max_tokens=self.merge_output_tokens,
                response_schema=None,
            )
            complete_validated = getattr(
                self.llm, "complete_text_validated", None
            )
            if callable(complete_validated):
                raw = await complete_validated(
                    validator=_parse_free_content,
                    **call_kwargs,
                )
            else:
                raw = await self.llm.complete_text(**call_kwargs)
            return _parse_free_content(raw), 1, None
        except Exception as exc:
            fallback = {
                "文档分段理解结果": [
                    {"页码范围": chunk.page_numbers, "内容": content}
                    for chunk, content in extracted_chunks
                ]
            }
            return fallback, 1, f"{type(exc).__name__}: {exc}"

    async def _extract_whole_pdf(
        self,
        *,
        pdf: bytes,
        filename: str,
        document_id: str,
        title: str,
        report_type: str,
        report_profile: dict | None,
    ) -> tuple[FreeExtractionResult, int]:
        last_error: str | None = None
        for attempt in range(1, self.maximum_total_attempts + 1):
            prompt = self.prompt_builder.build(
                document_id=document_id,
                title=title,
                report_type=report_type,
                report_profile=report_profile,
            )
            if last_error:
                prompt += f"\n\n上一次输出不是有效内容 JSON：{last_error}。请重新输出。"
            try:
                raw = await self.llm.complete_pdf(
                    prompt=prompt,
                    pdf=pdf,
                    filename=filename,
                    thinking_mode=self.thinking_mode,
                    max_tokens=self.merge_output_tokens,
                    response_schema=None,
                )
                content = _parse_free_content(raw)
                issues: list[str] = []
                _append_provider_issues(self.llm, issues)
                return FreeExtractionResult(
                    document_id=document_id,
                    report_type=report_type,
                    observed_title=title,
                    document_subtype=(report_profile or {}).get("sampling_subtype", "unknown"),
                    content=content,
                    chunk_count=1,
                    quality_issues=issues,
                ), attempt
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        issues: list[str] = []
        _append_provider_issues(self.llm, issues)
        return _unreadable_result(
            document_id,
            report_type,
            title,
            last_error or "unknown error",
            quality_issues=issues,
        ), self.maximum_total_attempts


def _unreadable_result(
    document_id: str,
    report_type: str,
    title: str,
    reason: str,
    *,
    source_page_count: int = 0,
    quality_issues: list[str] | None = None,
) -> FreeExtractionResult:
    return FreeExtractionResult(
        document_id=document_id,
        report_type=report_type,
        observed_title=title,
        readability=Readability.UNREADABLE,
        readability_reason=f"free document understanding failed: {reason}",
        source_page_count=source_page_count,
        quality_issues=quality_issues or [],
    )


def _append_provider_issues(llm: Any, issues: list[str]) -> None:
    consume_providers = getattr(llm, "consume_request_providers", None)
    if callable(consume_providers):
        issues.extend(
            f"LLM_PROVIDER_USED:{name}"
            for name in dict.fromkeys(consume_providers())
        )


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _parse_free_content_detailed(raw: str) -> tuple[dict[str, Any], bool]:
    recovered = False
    try:
        obj = json.loads(raw)
    except Exception:
        extracted = _extract_json_object(raw)
        if extracted is not None:
            obj = json.loads(extracted)
        else:
            obj = _recover_truncated_json_object(raw)
            recovered = True
    if not isinstance(obj, dict) or not obj:
        raise ValueError("response is not a non-empty JSON object")
    if isinstance(obj.get("content"), dict) and (
        {"document_id", "report_type", "readability", "observed_title"} & obj.keys()
    ):
        obj = obj["content"]
    if set(obj.keys()) <= _META_RESPONSE_KEYS:
        raise ValueError("model returned a status envelope instead of document content")
    if str(obj.get("readability", "")).upper() == "UNREADABLE" and len(obj) <= 2:
        raise ModelDeclaredChunkUnreadableError(
            str(obj.get("readability_reason") or "model marked content unreadable")
        )
    return obj, recovered


def _parse_free_content(raw: str) -> dict[str, Any]:
    """Parse free JSON; retain the last complete values if output was truncated."""
    return _parse_free_content_detailed(raw)[0]


def _recover_truncated_json_object(text: str) -> dict[str, Any]:
    """Recover complete properties/items from a truncated JSON object.

    At every comma outside a string, everything before that comma is a complete
    value. Closing the still-open containers preserves valid facts without
    accepting the unfinished value at the tail.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError("response has no JSON object")

    stack: list[str] = []
    candidates: list[tuple[int, tuple[str, ...]]] = []
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if stack:
                stack.pop()
        elif char == "," and stack:
            candidates.append((index, tuple(stack)))

    for end, open_containers in reversed(candidates):
        closers = "".join(
            "}" if char == "{" else "]" for char in reversed(open_containers)
        )
        try:
            value = json.loads(text[start:end].rstrip() + closers)
        except Exception:
            continue
        if isinstance(value, dict) and value:
            return value
    raise ValueError("response has no recoverable JSON object prefix")


def _find_subtype(content: dict[str, Any]) -> str | None:
    for key in _SUBTYPE_KEYS:
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

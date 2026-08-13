from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from dataclasses import dataclass

from atlas.core.clients import ExtractionRunStore, PDFObjectReader
from atlas.core.errors import AtlasError
from atlas.knowledge_production.extractor import FreeExtractionExtractor
from atlas.knowledge_production.pdf_preprocessor import PikePDFUnlocker
from atlas.models import ExtractionRun, ExtractionRunStatus, ResearchReport
from atlas.models.free_extraction import FreeExtractionResult


FREE_EXTRACTION_SCHEMA_VERSION = "free-document-understanding-v8"
FREE_DISCOVERY_SEMANTIC_VERSION = "free-discovery"


@dataclass(slots=True)
class FreeExtractionOutcome:
    run: ExtractionRun
    result: FreeExtractionResult | None


class FreeExtractionRunner:
    """Orchestrate one per-PDF free-form extraction for the discovery phase.

    Mirrors ``ExtractionOrchestrator``'s PDF read/unlock/store flow but uses
    ``FreeExtractionExtractor`` and records runs with a distinct schema version
    so free-extraction runs never collide with production atlas-extraction-v2
    runs (different prompt_signature + schema_version).
    """

    def __init__(
        self,
        *,
        reader: PDFObjectReader,
        store: ExtractionRunStore,
        extractor: FreeExtractionExtractor,
        unlocker: PikePDFUnlocker,
        pipeline_version: str,
    ) -> None:
        self.reader = reader
        self.store = store
        self.extractor = extractor
        self.unlocker = unlocker
        self.pipeline_version = pipeline_version

    async def run_document(
        self,
        report: ResearchReport,
        *,
        report_profile: dict | None = None,
    ) -> FreeExtractionOutcome:
        prompt_signature = self.extractor.prompt_builder.signature(
            report_profile or {}, self.extractor.llm.model_id
        )
        finder = getattr(self.store, "find_reusable_extraction", None)
        reusable = None
        if callable(finder):
            reusable = await finder(
                report.document_id,
                FREE_DISCOVERY_SEMANTIC_VERSION,
                self.pipeline_version,
                prompt_signature,
            )
        if reusable is not None:
            reusable_run, reusable_payload = reusable
            try:
                reusable_result = FreeExtractionResult.model_validate(reusable_payload)
            except Exception:
                reusable_result = None
            if reusable_result is not None and reusable_result.readable:
                return FreeExtractionOutcome(
                    run=reusable_run,
                    result=reusable_result,
                )
        run = ExtractionRun(
            source_document_id=report.document_id,
            source_report_type=report.report_type,
            pipeline_version=self.pipeline_version,
            model_id=self.extractor.llm.model_id,
            prompt_signature=prompt_signature,
            extraction_schema_version=FREE_EXTRACTION_SCHEMA_VERSION,
            semantic_version=FREE_DISCOVERY_SEMANTIC_VERSION,
            input_mode=getattr(self.extractor.llm, "input_mode", "PDF_DIRECT"),
        )
        await self.store.create_extraction_run(run)
        run.status = ExtractionRunStatus.PROCESSING
        run.started_at = datetime.now(UTC)
        await self.store.update_extraction_run(run)
        result: FreeExtractionResult | None = None
        try:
            source = await asyncio.to_thread(self.reader.read, report.pdf_object_key)
            run.pdf_size_bytes = len(source)
            unlocked = await asyncio.to_thread(self.unlocker.unlock, source)
            run.pdf_page_count = unlocked.page_count
            run.pdf_unlock_status = unlocked.status
            result, attempts = await self.extractor.extract(
                pdf=unlocked.content,
                filename=f"{report.resource_id}.pdf",
                document_id=report.document_id,
                title=report.title,
                report_type=report.report_type,
                report_profile=report_profile,
            )
            run.request_attempt_count = attempts
            run.possible_truncation = result.coverage_truncated
            run.last_page_referenced = max(result.covered_page_numbers, default=None)
            await self.store.save_extraction_result(
                run, result.model_dump(mode="json")
            )
            if result.readable and result.content:
                run.status = ExtractionRunStatus.SUCCEEDED
            else:
                run.status = ExtractionRunStatus.FAILED_RETRYABLE
                run.error_code = "FREE_DOCUMENT_UNREADABLE"
                run.error_summary = (result.readability_reason or "no document content")[:2000]
        except AtlasError as exc:
            run.status = ExtractionRunStatus.FAILED_RETRYABLE
            run.error_code = exc.code
            run.error_summary = str(exc)[:2000]
        except Exception as exc:
            run.status = ExtractionRunStatus.FAILED_RETRYABLE
            run.error_code = "UNEXPECTED_PIPELINE_ERROR"
            run.error_summary = str(exc)[:2000]
        finally:
            if run.status != ExtractionRunStatus.PROCESSING:
                run.completed_at = datetime.now(UTC)
            await self.store.update_extraction_run(run)
        return FreeExtractionOutcome(run=run, result=result)

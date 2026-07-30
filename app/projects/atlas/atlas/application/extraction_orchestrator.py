from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from dataclasses import dataclass

from atlas.core.clients import ExtractionRunStore, PDFObjectReader
from atlas.core.errors import AtlasError, ExtractionValidationError
from atlas.knowledge_production.extractor import WholePDFExtractor
from atlas.knowledge_production.pdf_preprocessor import PikePDFUnlocker
from atlas.models import ExtractionResult, ExtractionRun, ExtractionRunStatus, ResearchReport


@dataclass(slots=True)
class ExtractionOutcome:
    run: ExtractionRun
    result: ExtractionResult | None


class ExtractionOrchestrator:
    """Programmatic orchestration boundary for one whole-PDF extraction run."""

    def __init__(
        self,
        *,
        reader: PDFObjectReader,
        store: ExtractionRunStore,
        extractor: WholePDFExtractor,
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
        semantic_config: dict,
        report_profile: dict,
        force: bool = False,
    ) -> ExtractionRun:
        return (
            await self.run_document_with_result(
                report,
                semantic_config=semantic_config,
                report_profile=report_profile,
                force=force,
            )
        ).run

    async def run_document_with_result(
        self,
        report: ResearchReport,
        *,
        semantic_config: dict,
        report_profile: dict,
        force: bool = False,
        finalize_status: bool = True,
    ) -> ExtractionOutcome:
        prompt_signature = self.extractor.prompt_builder.signature(
            semantic_config["version"], report_profile, self.extractor.llm.model_id
        )
        finder = getattr(self.store, "find_reusable_extraction", None)
        if not force and finder is not None:
            reusable = await finder(
                report.document_id,
                semantic_config["version"],
                self.pipeline_version,
                prompt_signature,
            )
            if reusable is not None:
                reusable_run, reusable_payload = reusable
                return ExtractionOutcome(
                    run=reusable_run,
                    result=ExtractionResult.model_validate(reusable_payload),
                )
        run = ExtractionRun(
            source_document_id=report.document_id,
            source_report_type=report.report_type,
            pipeline_version=self.pipeline_version,
            model_id=self.extractor.llm.model_id,
            prompt_signature=prompt_signature,
            extraction_schema_version="atlas-extraction-v2",
            semantic_version=semantic_config["version"],
            input_mode=getattr(self.extractor.llm, "input_mode", "PDF_DIRECT"),
        )
        await self.store.create_extraction_run(run)
        run.status = ExtractionRunStatus.PROCESSING
        run.started_at = datetime.now(UTC)
        await self.store.update_extraction_run(run)
        result: ExtractionResult | None = None
        try:
            source = await asyncio.to_thread(
                self.reader.read, report.pdf_object_key
            )
            run.pdf_size_bytes = len(source)
            unlocked = await asyncio.to_thread(self.unlocker.unlock, source)
            run.pdf_page_count = unlocked.page_count
            run.pdf_unlock_status = unlocked.status
            result, attempts, validation_errors = await self.extractor.extract(
                pdf=unlocked.content,
                filename=f"{report.resource_id}.pdf",
                document_id=report.document_id,
                title=report.title,
                report_type=report.report_type,
                semantic_config=semantic_config,
                report_profile=report_profile,
                page_count=unlocked.page_count,
            )
            run.request_attempt_count = attempts
            run.validation_error_codes = validation_errors
            run.possible_truncation = result.document_assessment.possible_truncation
            run.last_page_referenced = result.document_assessment.last_page_referenced
            run.relation_claim_count = len(result.relation_claims)
            run.quantified_claim_count = len(result.quantified_claims)
            run.analyst_view_count = len(result.analyst_views)
            await self.store.save_extraction_result(run, result.model_dump(mode="json"))
            run.status = (
                ExtractionRunStatus.SUCCEEDED
                if finalize_status
                else ExtractionRunStatus.PROCESSING
            )
        except ExtractionValidationError as exc:
            run.status = ExtractionRunStatus.FAILED_RETRYABLE
            run.request_attempt_count = self.extractor.maximum_total_attempts
            run.validation_error_codes = exc.errors
            run.error_code = exc.code
            run.error_summary = str(exc)[:2000]
        except AtlasError as exc:
            run.status = ExtractionRunStatus.FAILED_RETRYABLE
            if exc.code in {
                "MODEL_PDF_UNREADABLE",
                "MODEL_TIMEOUT",
                "MODEL_REQUEST_FAILED",
                "PDF_TEXT_EXTRACTION_FAILED",
            }:
                run.request_attempt_count = max(1, run.request_attempt_count)
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
        return ExtractionOutcome(run=run, result=result)

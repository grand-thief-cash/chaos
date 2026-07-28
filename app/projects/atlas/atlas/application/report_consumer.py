from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from atlas.core.errors import NoEnabledReportTypesError
from atlas.knowledge_production.ontology_discovery import SemanticRegistry
from atlas.models import ExtractionRun, ResearchReport


class ExtractionBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published_from: str | None = None
    published_to: str | None = None
    report_types: list[str] | None = None
    limit: int = Field(default=100, ge=1, le=2000)
    force: bool = False


class ReportSource(Protocol):
    async def list_research_reports(self, **kwargs) -> list[ResearchReport]: ...
    async def find_completed_extraction_run(
        self,
        source_document_id: str,
        semantic_version: str,
        pipeline_version: str,
    ) -> ExtractionRun | None: ...


class ReportProcessor(Protocol):
    pipeline_version: str

    async def run_document(
        self,
        report: ResearchReport,
        *,
        semantic_config: dict,
        report_profile: dict,
        force: bool = False,
    ) -> ExtractionRun: ...


class ReportConsumer:
    def __init__(
        self,
        source: ReportSource,
        processor: ReportProcessor,
        semantics: SemanticRegistry,
    ) -> None:
        self.source = source
        self.processor = processor
        self.semantics = semantics

    async def run(self, request: ExtractionBatchRequest) -> list[ExtractionRun]:
        semantic = self.semantics.get()
        enabled = set(semantic.enabled_report_types)
        report_types = request.report_types or semantic.enabled_report_types
        report_types = [item for item in report_types if item in enabled]
        if not report_types:
            raise NoEnabledReportTypesError("no requested report type is enabled")
        reports = await self.source.list_research_reports(
            report_types=report_types,
            published_from=request.published_from,
            published_to=request.published_to,
            limit=request.limit,
        )
        runs = []
        for report in reports:
            profile = semantic.report_profile(report.report_type)
            if not request.force:
                existing = await self.source.find_completed_extraction_run(
                    report.document_id,
                    semantic.version,
                    self.processor.pipeline_version,
                )
                if existing is not None:
                    runs.append(existing)
                    continue
            runs.append(
                await self.processor.run_document(
                    report,
                    semantic_config=semantic.payload,
                    report_profile=profile,
                    force=request.force,
                )
            )
        return runs

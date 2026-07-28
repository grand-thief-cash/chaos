import pytest

from atlas.application import ExtractionBatchRequest, ReportConsumer
from atlas.core.errors import NoEnabledReportTypesError
from atlas.models import (
    ExtractionRun,
    ReportTypeAssessment,
    ResearchReport,
    SemanticVersion,
)


class Semantics:
    def __init__(self, enabled=True):
        self.value = SemanticVersion(
            version="v1",
            report_types=[
                ReportTypeAssessment(
                    report_type="stock",
                    sampled_document_count=1,
                    readable_document_count=1,
                    useful_document_count=1,
                    useful_ratio=1,
                    enabled_for_production=enabled,
                    prompt_profile_key="stock-v1" if enabled else None,
                    rationale="test",
                )
            ],
            predicates=[],
            concepts=[],
            assertion_types=[],
        )
    def get(self):
        return self.value


class Source:
    def __init__(self):
        self.report_types = None
        self.completed = None
    async def list_research_reports(self, **kwargs):
        self.report_types = kwargs["report_types"]
        return [ResearchReport(
            source="eastmoney", resource_id="1", report_type="stock",
            publish_date="2026-01-01", title="Report", org_name="Broker",
            pdf_object_key="stock/1.pdf", status="downloaded",
        )]
    async def find_completed_extraction_run(self, *args):
        return self.completed


class Extraction:
    pipeline_version = "test"
    def __init__(self):
        self.calls = 0

    async def run_document(self, report, **kwargs):
        self.calls += 1
        return type("Run", (), {"source_document_id": report.document_id})()


@pytest.mark.asyncio
async def test_report_consumer_resolves_active_report_types():
    source = Source()
    consumer = ReportConsumer(source, Extraction(), Semantics())  # type: ignore[arg-type]
    runs = await consumer.run(ExtractionBatchRequest())
    assert source.report_types == ["stock"]
    assert runs[0].source_document_id == "eastmoney:1"


@pytest.mark.asyncio
async def test_report_consumer_rejects_disabled_types():
    consumer = ReportConsumer(Source(), Extraction(), Semantics(False))  # type: ignore[arg-type]
    with pytest.raises(NoEnabledReportTypesError):
        await consumer.run(ExtractionBatchRequest(report_types=["stock"]))


@pytest.mark.asyncio
async def test_report_consumer_skips_completed_run_unless_forced():
    source = Source()
    source.completed = ExtractionRun(
        source_document_id="eastmoney:1",
        source_report_type="stock",
        pipeline_version="test",
        model_id="test",
        prompt_signature="test",
        extraction_schema_version="atlas-extraction-v2",
        semantic_version="v1",
    )
    processor = Extraction()
    consumer = ReportConsumer(source, processor, Semantics())  # type: ignore[arg-type]

    runs = await consumer.run(ExtractionBatchRequest())
    assert runs[0] is source.completed
    assert processor.calls == 0

    await consumer.run(ExtractionBatchRequest(force=True))
    assert processor.calls == 1

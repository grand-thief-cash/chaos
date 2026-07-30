from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from atlas.application.extraction_orchestrator import ExtractionOutcome
from atlas.application.semantic_discovery_service import SemanticDiscoveryService
from atlas.knowledge_production.ontology_discovery import (
    DiscoveryAggregator,
    SemanticRegistry,
    SemanticVersionBuilder,
    SemanticYamlPublisher,
)
from atlas.models import (
    DiscoveryDocumentResult,
    DiscoveryRun,
    ExtractionRun,
    ExtractionRunStatus,
    PredicateProposal,
    ProposalStatus,
    ResearchReport,
)
from atlas.knowledge_production.ontology_discovery import stratified_sample


def _document(report_type: str, useful: bool) -> DiscoveryDocumentResult:
    return DiscoveryDocumentResult(
        document_id=f"{report_type}:{useful}",
        report_type=report_type,
        readable=True,
        useful_for_graph=useful,
        usefulness_reason="has reusable relations" if useful else "only duplicated market data",
        recommended_prompt_profile_key="company-research-v1" if useful else None,
        predicate_proposals=[
            PredicateProposal(
                canonical_name="PRODUCES",
                display_name="生产",
                description="主体生产客体",
                subject_types=["COMPANY"],
                object_types=["PRODUCT"],
                aliases=["生产"],
                evidence_document_ids=[f"{report_type}:{useful}"],
            )
        ] if useful else [],
    )


def test_discovery_aggregation_and_version_publish(tmp_path: Path):
    aggregator = DiscoveryAggregator()
    documents = [_document("stock", True), _document("stock", True), _document("macro", False)]
    assessments = aggregator.aggregate_report_types(documents)
    predicates = aggregator.aggregate_predicates(documents)
    predicates[0].status = ProposalStatus.ACCEPTED
    run = DiscoveryRun(
        requested_sample_size=3,
        document_results=documents,
        report_type_assessments=assessments,
        predicate_proposals=predicates,
    )
    version = SemanticVersionBuilder().build(run, "atlas-semantic-v0002")
    path = SemanticYamlPublisher(tmp_path).publish(version)
    registry = SemanticRegistry(path)
    assert registry.get().enabled_report_types == ["stock"]
    assert registry.get().predicates[0].canonical_name == "PRODUCES"
    with pytest.raises(FileExistsError):
        SemanticYamlPublisher(tmp_path).publish(version)


def test_sample_balances_report_types_and_broker_institutions():
    reports = [
        ResearchReport(
            source="eastmoney",
            resource_id=str(index),
            report_type=report_type,
            publish_date=f"2026-01-0{index + 1}",
            title="Report",
            org_name=broker,
            pdf_object_key=f"{index}.pdf",
            status="downloaded",
        )
        for index, (report_type, broker) in enumerate([
            ("stock", "Broker A"),
            ("stock", "Broker A"),
            ("stock", "Broker B"),
            ("industry", "Broker A"),
            ("industry", "Broker B"),
        ])
    ]
    sampled = stratified_sample(reports, 4)
    assert {item.report_type for item in sampled} == {"stock", "industry"}
    assert {item.org_name for item in sampled} == {"Broker A", "Broker B"}


def test_predicate_aggregation_unions_observed_entity_types():
    first = _document("stock", True)
    second = _document("industry", True)
    second.predicate_proposals[0].subject_types = ["MATERIAL"]
    second.predicate_proposals[0].object_types = ["MARKET"]
    proposal = DiscoveryAggregator().aggregate_predicates([first, second])[0]
    assert proposal.subject_types == ["COMPANY", "MATERIAL"]
    assert proposal.object_types == ["MARKET", "PRODUCT"]


@pytest.mark.asyncio
async def test_failed_sample_is_counted_as_unreadable(tmp_path: Path):
    report = ResearchReport(
        source="eastmoney",
        resource_id="failed-1",
        report_type="stock",
        publish_date="2026-07-01",
        title="Unreadable report",
        org_name="Broker A",
        pdf_object_key="failed.pdf",
        status="downloaded",
    )

    class Repository:
        async def list_research_reports(self, **_):
            return [report]

        async def save_governance_record(self, kind, payload):
            return {"kind": kind, "payload": payload}

    class Extraction:
        async def run_document_with_result(self, *_args, **_kwargs):
            return ExtractionOutcome(
                run=ExtractionRun(
                    source_document_id=report.document_id,
                    source_report_type=report.report_type,
                    pipeline_version="atlas-kg-v1",
                    model_id="test-model",
                    prompt_signature="test-signature",
                    extraction_schema_version="atlas-extraction-v2",
                    semantic_version="atlas-semantic-v0001",
                    status=ExtractionRunStatus.FAILED_RETRYABLE,
                    error_code="MODEL_PDF_UNREADABLE",
                ),
                result=None,
            )

    class Semantic:
        version = "atlas-semantic-v0001"
        payload = {"version": version}

        def report_profile(self, *_args, **_kwargs):
            return {"prompt_profile_key": "company-research-v1"}

    class Registry:
        def get(self):
            return Semantic()

    class SampleStore:
        writes = []

        async def write(self, **kwargs):
            self.writes.append(kwargs)
            return "sample_output/20260720/stock/failed-1.json"

    sample_store = SampleStore()

    service = SemanticDiscoveryService(
        Repository(),
        Extraction(),
        Registry(),
        semantic_directory=tmp_path,
        sample_store=sample_store,
        clock=lambda: datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    result = await service.run(
        SimpleNamespace(
            report_types=["stock"],
            published_from=None,
            published_to=None,
            sample_size=1,
        )
    )
    assert result["document_results"][0]["readable"] is False
    assert result["report_type_assessments"][0]["sampled_document_count"] == 1
    assert result["report_type_assessments"][0]["useful_ratio"] == 0
    assert result["document_results"][0]["sample_output_object_key"] == (
        "sample_output/20260720/stock/failed-1.json"
    )
    assert len(sample_store.writes) == 1
    assert sample_store.writes[0]["extraction_result"] is None
    assert sample_store.writes[0]["sampled_at"].strftime("%Y%m%d") == "20260720"

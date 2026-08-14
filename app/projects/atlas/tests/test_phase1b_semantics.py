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
    extraction_to_discovery_result,
)
from atlas.models import (
    AssertionType,
    DiscoveryDocumentResult,
    DiscoveryRun,
    DocumentAssessment,
    EntityMention,
    EntityType,
    ExtractionResult,
    ExtractionRun,
    ExtractionRunStatus,
    Polarity,
    PredicateProposal,
    ProposalStatus,
    Readability,
    RelationClaimCandidate,
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


def test_small_sample_visits_every_report_type_before_reusing_a_type():
    report_types = ["stock", "industry", "macro", "strategy", "morning_report"]
    reports = [
        ResearchReport(
            source="eastmoney",
            resource_id=f"{report_type}-{index}",
            report_type=report_type,
            publish_date="2026-01-01",
            title=f"{subtype}报告",
            org_name=f"Broker {index}",
            pdf_object_key=f"{report_type}-{index}.pdf",
            status="downloaded",
        )
        for report_type in report_types
        for index, subtype in enumerate(["年报业绩点评", "首次覆盖公司深度", "月度策略"])
    ]
    sampled = stratified_sample(reports, len(report_types), seed=17)
    assert {item.report_type for item in sampled} == set(report_types)


def test_sample_balances_title_subtypes_and_seed_is_reproducible():
    from atlas.knowledge_production.ontology_discovery.sampler import infer_report_subtype

    reports = [
        ResearchReport(
            source="eastmoney",
            resource_id=str(index),
            report_type="stock",
            publish_date="2026-01-01",
            title=title,
            org_name="Broker A",
            pdf_object_key=f"{index}.pdf",
            status="downloaded",
        )
        for index, title in enumerate([
            "2025年报业绩点评",
            "重大合同事件点评",
            "首次覆盖公司深度",
            "另一篇2025年报业绩点评",
        ])
    ]
    first = stratified_sample(reports, 3, seed=7)
    repeated = stratified_sample(reports, 3, seed=7)
    assert [item.resource_id for item in first] == [item.resource_id for item in repeated]
    assert {infer_report_subtype(item) for item in first} == {
        "业绩点评", "事件点评", "公司深度"
    }


def test_field_review_conversion_preserves_core_conditional_and_rejections():
    from atlas.models.free_extraction import CategoryFieldReview

    common = {
        "description": "description",
        "knowledge_graph_role": "relation",
        "value_shape": "object",
        "applicability": "all documents",
        "rationale": "reusable",
        "priority": 1,
        "source_document_ids": ["d1", "d2"],
        "observed_json_paths": ["产业链.产品"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "stock",
        "reviewed_document_count": 2,
        "core_fields": [{
            **common,
            "field_name": "主营产品与服务",
            "scope": "CORE",
        }],
        "conditional_fields": [{
            **common,
            "field_name": "关键经营指标",
            "scope": "CONDITIONAL",
        }],
        "rejected_over_specific_fields": [{
            "observed_field": "污泥处理量",
            "reason": "too specific",
            "generalized_to": "关键经营指标",
            "source_document_ids": ["d1"],
        }],
    })
    summary = SemanticDiscoveryService._field_review_to_summary(
        review,
        sampled_document_count=2,
        readable_document_count=2,
    )
    assert [item["field_name"] for item in summary["core_fields"]] == ["主营产品与服务"]
    assert [item["field_name"] for item in summary["conditional_fields"]] == ["关键经营指标"]
    assert summary["rejected_over_specific_fields"][0]["observed_field"] == "污泥处理量"


def test_predicate_aggregation_unions_observed_entity_types():
    first = _document("stock", True)
    second = _document("industry", True)
    second.predicate_proposals[0].subject_types = ["MATERIAL"]
    second.predicate_proposals[0].object_types = ["MARKET"]
    proposal = DiscoveryAggregator().aggregate_predicates([first, second])[0]
    assert proposal.subject_types == ["COMPANY", "MATERIAL"]
    assert proposal.object_types == ["MARKET", "PRODUCT"]


def _extraction_with_predicate(canonical: str, object_type: EntityType) -> ExtractionResult:
    """One COMPANY subject and one object mention of ``object_type`` linked by a
    relation whose canonical predicate hint is ``canonical``."""
    return ExtractionResult(
        schema_version="atlas-extraction-v2",
        semantic_version="atlas-semantic-v0001",
        document_id="eastmoney:doc-1",
        document_assessment=DocumentAssessment(readability=Readability.READABLE),
        entity_mentions=[
            EntityMention(
                mention_id="m1",
                mention="甲公司",
                suggested_entity_type=EntityType.COMPANY,
                context="甲公司主营产品包括乙产品",
            ),
            EntityMention(
                mention_id="m2",
                mention="乙产品",
                suggested_entity_type=object_type,
                context="主营产品包括乙产品",
            ),
        ],
        relation_claims=[
            RelationClaimCandidate(
                candidate_id="r1",
                subject_mention_id="m1",
                subject_mention="甲公司",
                raw_predicate="主营产品包括",
                predicate_family="product",
                canonical_predicate_hint=canonical,
                object_mention_id="m2",
                object_mention="乙产品",
                assertion_type=AssertionType.OBSERVED_FACT,
                polarity=Polarity.AFFIRMED,
                evidence_quote="甲公司主营产品包括乙产品",
                extraction_confidence=0.9,
            ),
        ],
        quantified_claims=[],
        analyst_views=[],
        unknown_semantic_terms=[],
    )


def test_predicate_object_type_reconciled_from_predicate_name():
    """MAKES_PRODUCT with a COMPANY-typed object becomes COMPANY -> PRODUCT.

    Weaker models often fall back to COMPANY/OTHER for the object of a relation
    whose predicate name clearly implies a more specific type. The discovery
    converter reconciles the displayed object type from the predicate name so
    governance reviewers see COMPANY -> PRODUCT instead of COMPANY -> COMPANY.
    """
    result = extraction_to_discovery_result(
        _extraction_with_predicate("MAKES_PRODUCT", EntityType.COMPANY),
        "stock",
        "company-research-v1",
    )
    predicate = result.predicate_proposals[0]
    assert predicate.canonical_name == "MAKES_PRODUCT"
    assert predicate.subject_types == ["COMPANY"]
    assert predicate.object_types == ["PRODUCT"]


def test_specific_object_type_is_trusted_over_predicate_name_hint():
    """A specific extracted object type is never clobbered by the predicate-name
    hint (e.g. MAKES_PRODUCT over a MATERIAL object stays MATERIAL)."""
    result = extraction_to_discovery_result(
        _extraction_with_predicate("MAKES_PRODUCT", EntityType.MATERIAL),
        "stock",
        "company-research-v1",
    )
    assert result.predicate_proposals[0].object_types == ["MATERIAL"]


def test_predicate_without_type_token_is_left_untouched():
    """Predicates whose name carries no type token (HAS_SHAREHOLDER) keep the
    extracted types as-is, so legitimate COMPANY -> COMPANY relations survive."""
    result = extraction_to_discovery_result(
        _extraction_with_predicate("HAS_SHAREHOLDER", EntityType.COMPANY),
        "stock",
        "company-research-v1",
    )
    predicate = result.predicate_proposals[0]
    assert predicate.subject_types == ["COMPANY"]
    assert predicate.object_types == ["COMPANY"]


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


@pytest.mark.asyncio
async def test_run_sample_free_extraction_invokes_summariser_and_publishes_governance(tmp_path: Path):
    """In free-extraction mode each PDF goes through free_runner, the summariser
    proposes predicates for the whole category, and the governance record
    carries those proposals."""
    from atlas.application.free_extraction_runner import FreeExtractionOutcome
    from atlas.models import CategoryFieldSummary, FieldRecommendation
    from atlas.models.free_extraction import (
        CategoryDiscoverySummary,
        FreeExtractionResult,
        PredicateDiscovery,
    )

    report = ResearchReport(
        source="eastmoney",
        resource_id="r1",
        report_type="stock",
        publish_date="2026-07-01",
        title="Some report",
        org_name="Broker A",
        pdf_object_key="r1.pdf",
        status="downloaded",
    )

    free_result = FreeExtractionResult(
        document_id=report.document_id,
        report_type="stock",
        observed_title="Some report",
        readability=Readability.READABLE,
        content={
            "summary": "宁德时代主营锂电池",
            "relationships": [
                {"subject": "宁德时代", "predicate": "生产", "object": "锂电池", "evidence": "公司主营锂电池"}
            ],
        },
    )

    class Repository:
        def __init__(self):
            self.category_results = {}
            self.governance = None
            self.terminal_sampled_document_ids = None

        async def list_research_reports(self, **_):
            return [report]

        async def save_governance_record(self, kind, payload):
            self.governance = payload
            return {"kind": kind, "payload": payload}

        async def update_sample_run_status(self, *args, **kwargs):
            if len(args) >= 2 and args[1] in {"SUCCESS", "FAILED"}:
                self.terminal_sampled_document_ids = kwargs.get(
                    "sampled_document_ids"
                )
            return None

        async def update_sample_run_progress(self, *_, **__):
            return None

        async def create_sample_document_result(self, run_id, doc_id, document_id, report_type, *, extraction_run_id, status):
            return {"id": doc_id}

        async def update_sample_document_result(self, *_, **__):
            return None

        async def upsert_sample_category_result(self, run_id, report_type, raw_results, **__):
            self.category_results[report_type] = raw_results
            return {}

        async def update_sample_field_summary(self, *_, **__):
            return None

    class FreeRunner:
        async def run_document(self, rpt, *, report_profile=None):
            return FreeExtractionOutcome(
                run=ExtractionRun(
                    source_document_id=rpt.document_id,
                    source_report_type=rpt.report_type,
                    pipeline_version="atlas-kg-v1",
                    model_id="ling-3.0-flash",
                    prompt_signature="free-sig",
                    extraction_schema_version="free-extraction-v1",
                    semantic_version="free-discovery",
                    status=ExtractionRunStatus.SUCCEEDED,
                ),
                result=free_result,
            )

    class FreeSummariser:
        called_with = None

        async def summarise(self, report_type, free_results, evidence_document_ids=None):
            self.called_with = (report_type, [r.document_id for r in free_results])
            return CategoryDiscoverySummary(
                report_type=report_type,
                readability_summary="2/2 readable",
                predicates=[
                    PredicateDiscovery(
                        canonical_name="PRODUCES",
                        display_name="生产",
                        description="主体生产客体",
                        subject_types=["COMPANY"],
                        object_types=["PRODUCT"],
                        occurrence_count=1,
                    )
                ],
            )

        def to_document_result(self, report_type, free_results, summary):
            from atlas.models import ConceptProposal, PredicateProposal
            return DiscoveryDocumentResult(
                document_id=f"{report_type}:category",
                report_type=report_type,
                readable=True,
                useful_for_graph=True,
                usefulness_reason=summary.readability_summary,
                predicate_proposals=[
                    PredicateProposal(
                        canonical_name="PRODUCES",
                        display_name="生产",
                        description="主体生产客体",
                        subject_types=["COMPANY"],
                        object_types=["PRODUCT"],
                        evidence_document_ids=[r.document_id for r in free_results],
                    )
                ],
                concept_proposals=[],
            )

    class AgentClient:
        async def complete_model(self, model, *, system_prompt, user_prompt):
            return CategoryFieldSummary(
                report_type="stock",
                recommended_fields=[
                    FieldRecommendation(
                        field_name="products",
                        description="主营产品",
                        rationale="多次出现",
                    )
                ],
            )

    class FreeFieldReviewer:
        async def summarise(self, report_type, free_results):
            from atlas.models.free_extraction import CategoryFieldReview

            return CategoryFieldReview.model_validate({
                "report_type": report_type,
                "reviewed_document_count": len(free_results),
                "core_fields": [{
                    "field_name": "主营产品与服务",
                    "description": "公司提供的主要产品与服务",
                    "scope": "CORE",
                    "knowledge_graph_role": "COMPANY-PRODUCES-PRODUCT",
                    "value_shape": "list[object]",
                    "applicability": "所有公司研报",
                    "rationale": "产业链供给侧核心字段",
                    "priority": 1,
                    "source_document_ids": [item.document_id for item in free_results],
                    "observed_json_paths": ["summary"],
                }],
            })

    class Registry:
        def get(self):
            class S:
                version = "atlas-semantic-v0001"
                payload = {"version": version}

                def report_profile(self, *_a, **_k):
                    return {"prompt_profile_key": "company-research-v1"}

            return S()

    repo = Repository()
    summariser = FreeSummariser()
    service = SemanticDiscoveryService(
        repo,
        extraction=None,  # not used in free mode
        semantic_registry=Registry(),
        semantic_directory=tmp_path,
        agent_client=AgentClient(),
        free_runner=FreeRunner(),
        free_summariser=summariser,
        free_field_reviewer=FreeFieldReviewer(),
    )

    await service.run_sample(
        "11111111-2222-3333-4444-555555555555",
        SimpleNamespace(
            report_types=["stock"],
            published_from=None,
            published_to=None,
            sample_size=1,
        ),
    )

    # Summariser received the free extraction for the document.
    assert summariser.called_with == ("stock", [report.document_id])
    # raw_results carry the free extraction JSON, not a strict extraction_result.
    raw = repo.category_results["stock"][0]
    assert raw["extraction_result"] is None
    assert raw["free_extraction_result"]["content"]["summary"] == "宁德时代主营锂电池"
    # Governance record carries the summariser's predicate proposal.
    assert repo.governance is not None
    predicate_names = [
        p["canonical_name"] for p in repo.governance["predicate_proposals"]
    ]
    assert "PRODUCES" in predicate_names
    assert repo.terminal_sampled_document_ids == [report.document_id]


@pytest.mark.asyncio
async def test_run_sample_fetches_candidate_pool_per_requested_report_type(tmp_path: Path):
    """A database-global LIMIT must not starve later report types."""
    from atlas.application.free_extraction_runner import FreeExtractionOutcome
    from atlas.models.free_extraction import CategoryFieldReview, FreeExtractionResult

    def report(report_type: str) -> ResearchReport:
        return ResearchReport(
            source="eastmoney",
            resource_id=report_type,
            report_type=report_type,
            publish_date="2026-07-01",
            title=f"{report_type} report",
            org_name="Broker",
            pdf_object_key=f"{report_type}.pdf",
            status="downloaded",
        )

    reports = {item: report(item) for item in ("stock", "industry", "macro")}

    class Repository:
        def __init__(self):
            self.queries = []
            self.limits = []

        async def list_research_reports(self, **kwargs):
            self.queries.append(kwargs["report_types"])
            self.limits.append(kwargs["limit"])
            return [reports[kwargs["report_types"][0]]]

        async def update_sample_run_status(self, *_, **__): pass
        async def update_sample_run_progress(self, *_, **__): pass
        async def create_sample_document_result(self, *_, **__): return {}
        async def update_sample_document_result(self, *_, **__): pass
        async def upsert_sample_category_result(self, *_, **__): return {}
        async def update_sample_field_summary(self, *_, **__): pass
        async def save_governance_record(self, *_, **__): return {}

    class FreeRunner:
        async def run_document(self, rpt, **_):
            return FreeExtractionOutcome(
                run=ExtractionRun(
                    source_document_id=rpt.document_id,
                    source_report_type=rpt.report_type,
                    pipeline_version="test",
                    model_id="fake",
                    prompt_signature="sig",
                    extraction_schema_version="free-v1",
                    semantic_version="test",
                    status=ExtractionRunStatus.SUCCEEDED,
                ),
                result=FreeExtractionResult(
                    document_id=rpt.document_id,
                    report_type=rpt.report_type,
                    content={"研究对象": rpt.report_type},
                ),
            )

    class Reviewer:
        async def summarise(self, report_type, free_results):
            return CategoryFieldReview.model_validate({
                "report_type": report_type,
                "core_fields": [{
                    "field_name": "研究对象",
                    "description": "研究主题",
                    "scope": "CORE",
                    "knowledge_graph_role": "topic",
                    "value_shape": "string",
                    "applicability": "所有报告",
                    "rationale": "输入明确",
                    "priority": 1,
                    "source_document_ids": [free_results[0].document_id],
                    "observed_json_paths": ["研究对象"],
                }],
            })

    class Registry:
        def get(self):
            class Semantic:
                def report_profile(self, *_a, **_k): return {}
            return Semantic()

    repo = Repository()
    service = SemanticDiscoveryService(
        repo,
        extraction=None,
        semantic_registry=Registry(),
        semantic_directory=tmp_path,
        free_runner=FreeRunner(),
        free_summariser=None,
        free_field_reviewer=Reviewer(),
    )
    await service.run_sample(
        "11111111-2222-3333-4444-555555555556",
        SimpleNamespace(
            report_types=["stock", "industry", "macro"],
            published_from=None,
            published_to=None,
            sample_size=3,
            sample_seed=1,
        ),
    )
    assert repo.queries == [["stock"], ["industry"], ["macro"]]
    # A broad metadata-only candidate pool is intentional: it gives the
    # stratifier enough title/subtype diversity before any PDF or LLM expense.
    assert repo.limits == [80, 80, 80]


@pytest.mark.asyncio
async def test_run_sample_checkpoints_free_json_after_each_document(tmp_path: Path):
    """Completed paid work is durable before the next PDF starts."""
    from atlas.application.free_extraction_runner import FreeExtractionOutcome
    from atlas.models.free_extraction import CategoryFieldReview, FreeExtractionResult

    reports = [
        ResearchReport(
            source="eastmoney",
            resource_id=str(index),
            report_type="stock",
            publish_date="2026-07-01",
            title=f"report {index}",
            org_name="Broker",
            pdf_object_key=f"{index}.pdf",
            status="downloaded",
        )
        for index in range(2)
    ]

    class Repository:
        def __init__(self):
            self.checkpoint_sizes = []

        async def list_research_reports(self, **_): return reports
        async def update_sample_run_status(self, *_, **__): pass
        async def update_sample_run_progress(self, *_, **__): pass
        async def create_sample_document_result(self, *_, **__): return {}
        async def update_sample_document_result(self, *_, **__): pass
        async def update_sample_field_summary(self, *_, **__): pass
        async def save_governance_record(self, *_, **__): return {}

        async def upsert_sample_category_result(self, _run, _type, raw_results, **_):
            self.checkpoint_sizes.append(len(raw_results))
            return {}

    class FreeRunner:
        async def run_document(self, rpt, **_):
            return FreeExtractionOutcome(
                run=ExtractionRun(
                    source_document_id=rpt.document_id,
                    source_report_type="stock",
                    pipeline_version="test",
                    model_id="fake",
                    prompt_signature="sig",
                    extraction_schema_version="free-v1",
                    semantic_version="test",
                    status=ExtractionRunStatus.SUCCEEDED,
                ),
                result=FreeExtractionResult(
                    document_id=rpt.document_id,
                    report_type="stock",
                    content={"主营产品": "芯片"},
                ),
            )

    class Reviewer:
        async def summarise(self, _report_type, free_results):
            return CategoryFieldReview.model_validate({
                "report_type": "stock",
                "core_fields": [{
                    "field_name": "主营产品与服务",
                    "description": "公司供给",
                    "scope": "CORE",
                    "knowledge_graph_role": "PRODUCES",
                    "value_shape": "array",
                    "applicability": "公司研报",
                    "rationale": "输入明确",
                    "priority": 1,
                    "source_document_ids": [item.document_id for item in free_results],
                    "observed_json_paths": ["主营产品"],
                }],
            })

    class Registry:
        def get(self):
            class Semantic:
                def report_profile(self, *_a, **_k): return {}
            return Semantic()

    repo = Repository()
    service = SemanticDiscoveryService(
        repo,
        extraction=None,
        semantic_registry=Registry(),
        semantic_directory=tmp_path,
        free_runner=FreeRunner(),
        free_summariser=None,
        free_field_reviewer=Reviewer(),
    )
    await service.run_sample(
        "11111111-2222-3333-4444-555555555557",
        SimpleNamespace(
            report_types=["stock"],
            published_from=None,
            published_to=None,
            sample_size=2,
            sample_seed=1,
        ),
    )
    assert repo.checkpoint_sizes[:2] == [1, 2]

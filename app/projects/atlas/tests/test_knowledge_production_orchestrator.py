from uuid import uuid4

import pytest

from atlas.application.extraction_orchestrator import ExtractionOutcome
from atlas.application.knowledge_production_orchestrator import (
    KnowledgeProductionOrchestrator,
)
from atlas.models import (
    AnalystViewCandidate,
    AssertionType,
    DocumentAssessment,
    EntityCandidate,
    EntityMention,
    EntityType,
    ExtractionResult,
    ExtractionRun,
    KnowledgeEntity,
    Readability,
    RelationClaimCandidate,
    ResearchReport,
    ResolutionState,
)
from atlas.knowledge_production.entity_resolver import EntityResolutionService


class Extraction:
    async def run_document_with_result(self, report, **kwargs):
        result = ExtractionResult(
            schema_version="atlas-extraction-v2",
            semantic_version="v1",
            document_id=report.document_id,
            document_assessment=DocumentAssessment(
                readability=Readability.READABLE
            ),
            entity_mentions=[
                EntityMention(
                    mention_id="a",
                    mention="Company A",
                    suggested_entity_type=EntityType.COMPANY,
                    context="Company A supplies Company B.",
                ),
                EntityMention(
                    mention_id="b",
                    mention="Company B",
                    suggested_entity_type=EntityType.COMPANY,
                    context="Company A supplies Company B.",
                ),
            ],
            relation_claims=[
                RelationClaimCandidate(
                    candidate_id="r1",
                    subject_mention_id="a",
                    subject_mention="Company A",
                    raw_predicate="supplies",
                    predicate_family="SUPPLY_CHAIN",
                    canonical_predicate_hint="SUPPLIES",
                    object_mention_id="b",
                    object_mention="Company B",
                    assertion_type=AssertionType.OBSERVED_FACT,
                    evidence_quote="Company A supplies Company B.",
                    extraction_confidence=0.95,
                ),
                RelationClaimCandidate(
                    candidate_id="r2",
                    subject_mention_id="b",
                    subject_mention="Company B",
                    raw_predicate="plans to purchase from",
                    predicate_family="SUPPLY_CHAIN",
                    canonical_predicate_hint="PURCHASES_FROM",
                    object_mention_id="a",
                    object_mention="Company A",
                    assertion_type=AssertionType.MANAGEMENT_PLAN,
                    evidence_quote="Company B plans to purchase from Company A.",
                    extraction_confidence=0.8,
                ),
            ],
            quantified_claims=[],
            analyst_views=[
                AnalystViewCandidate(
                    candidate_id="v1",
                    subject_mention_id="a",
                    subject_mention="Company A",
                    summary="The analyst expects demand to improve.",
                    evidence_quote="We expect demand to improve.",
                    extraction_confidence=0.7,
                )
            ],
            unknown_semantic_terms=[],
        )
        return ExtractionOutcome(
            run=ExtractionRun(
                source_document_id=report.document_id,
                source_report_type=report.report_type,
                pipeline_version="test",
                model_id="test",
                prompt_signature="test",
                extraction_schema_version="atlas-extraction-v2",
                semantic_version="v1",
            ),
            result=result,
        )


class Candidates:
    async def find_candidates(self, normalized_name, entity_type, ticker_hint):
        entity = KnowledgeEntity(
            id=uuid4(),
            canonical_name=normalized_name,
            normalized_name=normalized_name,
            entity_type=entity_type,
            resolution_state=ResolutionState.RESOLVED_KNOWLEDGE_ENTITY,
        )
        return [EntityCandidate(entity=entity, score=1)]


class Store:
    def __init__(self):
        self.entities = []
        self.links = []
        self.aliases = []
        self.relations = []
        self.quantified = []
        self.views = []
        self.projected = []
        self.runs = []

    async def update_extraction_run(self, run):
        self.runs.append(run.model_copy(deep=True))

    async def upsert_knowledge_entities(self, entities):
        self.entities = entities

    async def upsert_security_entity_links(self, links):
        self.links = links

    async def upsert_entity_aliases(self, aliases):
        self.aliases = aliases

    async def upsert_claims(self, relations, quantified, views):
        self.relations = relations
        self.quantified = quantified
        self.views = views

    async def project_graph(self, entities, claims):
        self.projected = claims


@pytest.mark.asyncio
async def test_production_persists_all_claims_but_projects_only_facts():
    store = Store()
    orchestrator = KnowledgeProductionOrchestrator(
        Extraction(),  # type: ignore[arg-type]
        EntityResolutionService(Candidates()),
        store,
    )
    report = ResearchReport(
        source="eastmoney",
        resource_id="1",
        report_type="stock",
        publish_date="2026-01-01",
        title="Report",
        org_name="Broker",
        pdf_object_key="stock/1.pdf",
        status="downloaded",
    )

    await orchestrator.run_document(
        report,
        semantic_config={"version": "v1"},
        report_profile={},
    )

    assert len(store.entities) == 2
    assert {alias.alias for alias in store.aliases} == {"Company A", "Company B"}
    assert len(store.relations) == 2
    assert len(store.views) == 1
    assert [claim.canonical_predicate for claim in store.projected] == ["SUPPLIES"]

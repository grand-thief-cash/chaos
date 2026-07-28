from uuid import uuid4

from atlas.knowledge_production.claim_builder import (
    build_analyst_views,
    build_quantified_claims,
    build_relation_claims,
)
from atlas.models import (
    AnalystViewCandidate,
    AssertionType,
    DocumentAssessment,
    EntityMention,
    EntityType,
    ExtractionResult,
    KnowledgeEntity,
    QuantifiedClaimCandidate,
    Polarity,
    Readability,
    ResolutionState,
    ResolvedMention,
    RelationClaimCandidate,
)


def test_quantified_claim_and_analyst_view_keep_assertion_semantics():
    entity = KnowledgeEntity(
        id=uuid4(),
        canonical_name="Company A",
        normalized_name="companya",
        entity_type="COMPANY",
        resolution_state=ResolutionState.PROVISIONAL,
    )
    resolution = ResolvedMention(
        mention_id="m1", entity=entity, confidence=0.8, method="PROVISIONAL"
    )
    extraction = ExtractionResult(
        schema_version="atlas-extraction-v2",
        semantic_version="v1",
        document_id="report:1",
        document_assessment=DocumentAssessment(
            readability=Readability.READABLE,
            observed_title="Report",
            possible_truncation=True,
        ),
        entity_mentions=[
            EntityMention(
                mention_id="m1",
                mention="Company A",
                suggested_entity_type=EntityType.COMPANY,
                context="Company A plans capacity expansion",
            )
        ],
        relation_claims=[],
        quantified_claims=[
            QuantifiedClaimCandidate(
                candidate_id="q1",
                subject_mention_id="m1",
                subject_mention="Company A",
                metric_raw_name="capacity",
                value=120,
                value_text="120 GWh",
                unit="GWh",
                period="2027",
                change_type="INCREASE_TO",
                base_value=80,
                target_value=120,
                assertion_type=AssertionType.MANAGEMENT_PLAN,
                evidence_quote="plans 120 GWh capacity in 2027",
                extraction_confidence=0.8,
            )
        ],
        analyst_views=[
            AnalystViewCandidate(
                candidate_id="v1",
                subject_mention_id="m1",
                subject_mention="Company A",
                summary="Capacity execution is the key catalyst",
                evidence_quote="execution is the key catalyst",
                extraction_confidence=0.7,
            )
        ],
        unknown_semantic_terms=[],
    )
    quantified = build_quantified_claims(extraction, [resolution])
    views = build_analyst_views(extraction, [resolution])
    assert quantified[0].assertion_type == AssertionType.MANAGEMENT_PLAN
    assert quantified[0].value_text == "120 GWh"
    assert quantified[0].base_value == 80
    assert quantified[0].target_value == 120
    assert views[0].assertion_type == AssertionType.ANALYST_OPINION
    assert views[0].subject_entity_id == entity.id
    assert quantified[0].status == "REVIEW_REQUIRED"
    assert views[0].status == "REVIEW_REQUIRED"


def test_relation_quality_gate_rejects_negation_and_holds_truncated_documents():
    subject = KnowledgeEntity(
        canonical_name="Company A",
        normalized_name="companya",
        entity_type="COMPANY",
        resolution_state=ResolutionState.PROVISIONAL,
    )
    object_ = KnowledgeEntity(
        canonical_name="Product B",
        normalized_name="productb",
        entity_type="PRODUCT",
        resolution_state=ResolutionState.PROVISIONAL,
    )
    resolutions = [
        ResolvedMention(
            mention_id="m1",
            entity=subject,
            confidence=0.8,
            method="PROVISIONAL",
        ),
        ResolvedMention(
            mention_id="m2",
            entity=object_,
            confidence=0.8,
            method="PROVISIONAL",
        ),
    ]
    extraction = ExtractionResult(
        schema_version="atlas-extraction-v2",
        semantic_version="v1",
        document_id="report:2",
        document_assessment=DocumentAssessment(
            readability=Readability.READABLE,
            possible_truncation=True,
        ),
        entity_mentions=[
            EntityMention(
                mention_id="m1",
                mention="Company A",
                suggested_entity_type=EntityType.COMPANY,
                context="Company A does not produce Product B.",
            ),
            EntityMention(
                mention_id="m2",
                mention="Product B",
                suggested_entity_type=EntityType.PRODUCT,
                context="Company A does not produce Product B.",
            ),
        ],
        relation_claims=[
            RelationClaimCandidate(
                candidate_id="r1",
                subject_mention_id="m1",
                subject_mention="Company A",
                raw_predicate="does not produce",
                predicate_family="PRODUCT",
                canonical_predicate_hint="PRODUCES",
                object_mention_id="m2",
                object_mention="Product B",
                assertion_type=AssertionType.OBSERVED_FACT,
                polarity=Polarity.NEGATED,
                evidence_quote="Company A does not produce Product B.",
                extraction_confidence=0.9,
            ),
            RelationClaimCandidate(
                candidate_id="r2",
                subject_mention_id="m1",
                subject_mention="Company A",
                raw_predicate="produces",
                predicate_family="PRODUCT",
                canonical_predicate_hint="PRODUCES",
                object_mention_id="m2",
                object_mention="Product B",
                assertion_type=AssertionType.OBSERVED_FACT,
                evidence_quote="Company A produces Product B.",
                extraction_confidence=0.8,
            ),
        ],
        quantified_claims=[],
        analyst_views=[],
        unknown_semantic_terms=[],
    )
    claims = build_relation_claims(
        extraction,
        resolutions,
        {
            "predicates": [{
                "canonical_name": "PRODUCES",
                "status": "ACCEPTED",
                "subject_types": ["COMPANY"],
                "object_types": ["PRODUCT"],
            }]
        },
    )
    statuses = {claim.polarity: claim.status for claim in claims}
    assert statuses[Polarity.NEGATED] == "REJECTED"
    assert statuses[Polarity.AFFIRMED] == "REVIEW_REQUIRED"

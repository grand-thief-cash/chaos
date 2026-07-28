from __future__ import annotations

from atlas.models import (
    ConceptProposal,
    DiscoveryDocumentResult,
    ExtractionResult,
    PredicateProposal,
)


def extraction_to_discovery_result(
    extraction: ExtractionResult,
    report_type: str,
    prompt_profile_key: str,
) -> DiscoveryDocumentResult:
    mentions = {
        mention.mention_id: mention
        for mention in extraction.entity_mentions
    }
    predicates: dict[str, PredicateProposal] = {}
    for claim in extraction.relation_claims:
        canonical = claim.canonical_predicate_hint
        if canonical is None:
            continue
        subject = mentions[claim.subject_mention_id]
        object_ = mentions[claim.object_mention_id]
        if canonical not in predicates:
            predicates[canonical] = PredicateProposal(
                canonical_name=canonical,
                display_name=claim.raw_predicate,
                description=f"Discovered from report relation: {claim.raw_predicate}",
                subject_types=[subject.suggested_entity_type.value],
                object_types=[object_.suggested_entity_type.value],
                aliases=[claim.raw_predicate],
                evidence_document_ids=[extraction.document_id],
            )
        else:
            predicates[canonical].occurrence_count += 1

    concepts: dict[tuple[str, str], ConceptProposal] = {}
    for mention in extraction.entity_mentions:
        if mention.suggested_entity_type.value == "COMPANY":
            continue
        key = (mention.suggested_entity_type.value, mention.mention)
        concepts.setdefault(
            key,
            ConceptProposal(
                concept_type=mention.suggested_entity_type.value,
                canonical_name=mention.mention,
                display_name=mention.mention,
                description=f"Discovered {mention.suggested_entity_type.value.lower()} concept",
                evidence_document_ids=[extraction.document_id],
            ),
        )

    useful = bool(
        extraction.relation_claims
        or extraction.quantified_claims
        or extraction.analyst_views
    )
    return DiscoveryDocumentResult(
        document_id=extraction.document_id,
        report_type=report_type,
        readable=True,
        useful_for_graph=useful,
        usefulness_reason=(
            "Contains reusable relations, quantified claims, or analyst views"
            if useful
            else "No reusable knowledge was extracted"
        ),
        recommended_prompt_profile_key=prompt_profile_key if useful else None,
        predicate_proposals=list(predicates.values()),
        concept_proposals=list(concepts.values()),
    )

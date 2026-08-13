from __future__ import annotations

from atlas.models import (
    ConceptProposal,
    DiscoveryDocumentResult,
    EntityType,
    ExtractionResult,
    PredicateProposal,
)

# EntityType values a canonical predicate name can imply. COMPANY and OTHER are
# excluded: they are generic catch-alls, never a type we would force from a name
# token. Keys are the UPPER_SNAKE EntityType values; multi-token values
# (INDUSTRY_CLASS, VALUE_CHAIN) are matched as trailing name segments.
IMPLIED_TYPE_TOKENS = frozenset(
    member.value
    for member in EntityType
    if member not in (EntityType.COMPANY, EntityType.OTHER)
)

# Entity types that act as a generic placeholder and may be overridden when the
# predicate name implies a more specific type.
_GENERIC_ENTITY_TYPES = frozenset((EntityType.COMPANY.value, EntityType.OTHER.value))


def _implied_object_type(canonical: str | None) -> str | None:
    """Infer the object entity type from a trailing type token in the predicate
    name (e.g. ``MAKES_PRODUCT`` -> ``PRODUCT``, ``USES_MATERIAL`` -> ``MATERIAL``,
    ``BELONGS_TO_INDUSTRY_CLASS`` -> ``INDUSTRY_CLASS``).

    Only the trailing segment is considered, so metric-like predicates such as
    ``MARKET_SHARE`` are not affected (``SHARE`` is not a type token). Returns
    ``None`` when no type token is present.
    """
    if not canonical:
        return None
    for value in IMPLIED_TYPE_TOKENS:
        if canonical == value or canonical.endswith("_" + value):
            return value
    return None


def _reconcile_object_type(extracted: str, implied: str | None) -> str:
    """Prefer the type implied by the predicate name when the model fell back to
    a generic placeholder (COMPANY/OTHER). A specific extracted type is always
    trusted over the name-derived hint.
    """
    if implied is not None and extracted in _GENERIC_ENTITY_TYPES:
        return implied
    return extracted


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
        # Skip self-references: weaker models often fill the object with the
        # subject entity itself for metric-like predicates (FORECASTS_REVENUE,
        # HAS_MARKET_SHARE, ...) that have no natural entity object. These
        # belong in quantified_claims, and a COMPANY -> COMPANY self-edge is
        # never a useful reusable predicate, so drop it from discovery.
        if claim.subject_mention_id == claim.object_mention_id:
            continue
        subject = mentions[claim.subject_mention_id]
        object_ = mentions[claim.object_mention_id]
        if canonical not in predicates:
            # Reconcile the object type against the predicate name: weaker
            # models often fall back to COMPANY/OTHER for the object of a
            # relation whose predicate name clearly implies a more specific
            # type (e.g. ``MAKES_PRODUCT`` -> the object is a PRODUCT, not a
            # COMPANY). Only generic placeholders are corrected; a specific
            # extracted type is always trusted.
            implied_object = _implied_object_type(canonical)
            object_type = _reconcile_object_type(
                object_.suggested_entity_type.value, implied_object
            )
            predicates[canonical] = PredicateProposal(
                canonical_name=canonical,
                display_name=claim.raw_predicate,
                description=f"Discovered from report relation: {claim.raw_predicate}",
                subject_types=[subject.suggested_entity_type.value],
                object_types=[object_type],
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

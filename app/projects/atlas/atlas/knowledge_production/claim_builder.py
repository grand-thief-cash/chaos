import json

from atlas.models import (
    AnalystView,
    ExtractionResult,
    QuantifiedClaim,
    RelationClaim,
    ResolvedMention,
    Polarity,
)


def build_relation_claims(
    extraction: ExtractionResult,
    resolutions: list[ResolvedMention],
    semantic_config: dict | None = None,
) -> list[RelationClaim]:
    by_mention = {item.mention_id: item for item in resolutions}
    predicate_definitions = {
        item["canonical_name"]: item
        for item in (semantic_config or {}).get("predicates", [])
        if item.get("status") in (None, "ACCEPTED")
    }
    output: list[RelationClaim] = []
    for candidate in extraction.relation_claims:
        if not candidate.canonical_predicate_hint:
            continue
        subject = by_mention.get(candidate.subject_mention_id)
        object_ = by_mention.get(candidate.object_mention_id)
        if not subject or not object_:
            continue
        status = "ACCEPTED"
        definition = predicate_definitions.get(candidate.canonical_predicate_hint)
        if predicate_definitions and definition is None:
            status = "REVIEW_REQUIRED"
        elif definition is not None:
            subject_types = set(definition.get("subject_types") or [])
            object_types = set(definition.get("object_types") or [])
            if (
                subject_types
                and subject.entity.entity_type not in subject_types
            ) or (
                object_types
                and object_.entity.entity_type not in object_types
            ):
                status = "REJECTED"
        if candidate.polarity != Polarity.AFFIRMED:
            status = "REJECTED"
        if extraction.document_assessment.possible_truncation and status == "ACCEPTED":
            status = "REVIEW_REQUIRED"
        output.append(RelationClaim(
            source_document_id=extraction.document_id,
            subject_entity_id=subject.entity.id,
            object_entity_id=object_.entity.id,
            canonical_predicate=candidate.canonical_predicate_hint,
            assertion_type=candidate.assertion_type,
            polarity=candidate.polarity,
            confidence=candidate.extraction_confidence,
            evidence_quote=candidate.evidence_quote,
            page_number=candidate.page_number,
            valid_from=(
                str(candidate.valid_from) if candidate.valid_from else None
            ),
            valid_to=str(candidate.valid_to) if candidate.valid_to else None,
            qualifiers=candidate.qualifiers,
            status=status,
        ))
    deduplicated: dict[tuple, RelationClaim] = {}
    for claim in output:
        key = (
            claim.subject_entity_id,
            claim.canonical_predicate,
            claim.object_entity_id,
            claim.assertion_type,
            claim.polarity,
            json.dumps(claim.qualifiers, sort_keys=True, default=str),
        )
        current = deduplicated.get(key)
        if current is None or claim.confidence > current.confidence:
            deduplicated[key] = claim
    return list(deduplicated.values())


def build_quantified_claims(
    extraction: ExtractionResult,
    resolutions: list[ResolvedMention],
) -> list[QuantifiedClaim]:
    by_mention = {item.mention_id: item for item in resolutions}
    output: list[QuantifiedClaim] = []
    for candidate in extraction.quantified_claims:
        subject = by_mention.get(candidate.subject_mention_id)
        if not subject:
            continue
        output.append(QuantifiedClaim(
            source_document_id=extraction.document_id,
            subject_entity_id=subject.entity.id,
            metric_raw_name=candidate.metric_raw_name,
            metric_hint=candidate.metric_hint,
            value=candidate.value,
            value_text=candidate.value_text,
            unit=candidate.unit,
            period=candidate.period,
            change_type=candidate.change_type,
            base_value=candidate.base_value,
            target_value=candidate.target_value,
            assertion_type=candidate.assertion_type,
            confidence=candidate.extraction_confidence,
            evidence_quote=candidate.evidence_quote,
            page_number=candidate.page_number,
            qualifiers=candidate.qualifiers,
            status=(
                "REVIEW_REQUIRED"
                if extraction.document_assessment.possible_truncation
                else "ACCEPTED"
            ),
        ))
    return output


def build_analyst_views(
    extraction: ExtractionResult,
    resolutions: list[ResolvedMention],
) -> list[AnalystView]:
    by_mention = {item.mention_id: item for item in resolutions}
    output: list[AnalystView] = []
    for candidate in extraction.analyst_views:
        subject = (
            by_mention.get(candidate.subject_mention_id)
            if candidate.subject_mention_id
            else None
        )
        output.append(AnalystView(
            source_document_id=extraction.document_id,
            subject_entity_id=subject.entity.id if subject else None,
            view_type_hint=candidate.view_type_hint,
            stance=candidate.stance,
            summary=candidate.summary,
            time_horizon=candidate.time_horizon,
            assertion_type=candidate.assertion_type,
            confidence=candidate.extraction_confidence,
            evidence_quote=candidate.evidence_quote,
            page_number=candidate.page_number,
            attributes=candidate.attributes,
            status=(
                "REVIEW_REQUIRED"
                if extraction.document_assessment.possible_truncation
                else "ACCEPTED"
            ),
        ))
    return output

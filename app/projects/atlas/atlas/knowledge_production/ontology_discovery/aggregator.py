from __future__ import annotations

from collections import defaultdict

from atlas.models import (
    ConceptProposal,
    DiscoveryDocumentResult,
    PredicateProposal,
    ReportTypeAssessment,
)


class DiscoveryAggregator:
    def aggregate_report_types(
        self, results: list[DiscoveryDocumentResult]
    ) -> list[ReportTypeAssessment]:
        groups: dict[str, list[DiscoveryDocumentResult]] = defaultdict(list)
        for result in results:
            groups[result.report_type].append(result)
        assessments: list[ReportTypeAssessment] = []
        for report_type, items in sorted(groups.items()):
            readable = sum(item.readable for item in items)
            useful = sum(item.useful_for_graph for item in items)
            ratio = useful / len(items)
            profiles = [
                item.recommended_prompt_profile_key
                for item in items
                if item.useful_for_graph and item.recommended_prompt_profile_key
            ]
            profile = max(set(profiles), key=profiles.count) if profiles else None
            assessments.append(
                ReportTypeAssessment(
                    report_type=report_type,
                    sampled_document_count=len(items),
                    readable_document_count=readable,
                    useful_document_count=useful,
                    useful_ratio=ratio,
                    enabled_for_production=ratio >= 0.5 and profile is not None,
                    prompt_profile_key=profile,
                    rationale=f"{useful}/{len(items)} samples contain reusable graph knowledge",
                )
            )
        return assessments

    def aggregate_predicates(
        self, results: list[DiscoveryDocumentResult]
    ) -> list[PredicateProposal]:
        grouped: dict[str, list[PredicateProposal]] = defaultdict(list)
        for result in results:
            for proposal in result.predicate_proposals:
                grouped[proposal.canonical_name].append(proposal)
        output: list[PredicateProposal] = []
        for canonical_name, proposals in sorted(grouped.items()):
            representative = proposals[0].model_copy(deep=True)
            representative.occurrence_count = sum(item.occurrence_count for item in proposals)
            representative.aliases = sorted({alias for item in proposals for alias in item.aliases})
            representative.subject_types = sorted({
                entity_type
                for item in proposals
                for entity_type in item.subject_types
            })
            representative.object_types = sorted({
                entity_type
                for item in proposals
                for entity_type in item.object_types
            })
            representative.evidence_document_ids = sorted({
                document_id
                for item in proposals
                for document_id in item.evidence_document_ids
            })
            output.append(representative)
        return output

    def aggregate_concepts(
        self, results: list[DiscoveryDocumentResult]
    ) -> list[ConceptProposal]:
        grouped: dict[tuple[str, str], list[ConceptProposal]] = defaultdict(list)
        for result in results:
            for proposal in result.concept_proposals:
                grouped[(proposal.concept_type, proposal.canonical_name)].append(proposal)
        output: list[ConceptProposal] = []
        for _, proposals in sorted(grouped.items()):
            representative = proposals[0].model_copy(deep=True)
            representative.occurrence_count = sum(item.occurrence_count for item in proposals)
            representative.aliases = sorted({alias for item in proposals for alias in item.aliases})
            representative.evidence_document_ids = sorted({
                document_id
                for item in proposals
                for document_id in item.evidence_document_ids
            })
            output.append(representative)
        return output

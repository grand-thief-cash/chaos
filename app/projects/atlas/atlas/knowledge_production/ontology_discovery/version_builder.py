from __future__ import annotations

from datetime import UTC, datetime

from atlas.models import DiscoveryRun, ProposalStatus, SemanticVersion


class SemanticVersionBuilder:
    def build(self, discovery: DiscoveryRun, version: str) -> SemanticVersion:
        accepted_predicates = [
            item for item in discovery.predicate_proposals if item.status == ProposalStatus.ACCEPTED
        ]
        accepted_concepts = [
            item for item in discovery.concept_proposals if item.status == ProposalStatus.ACCEPTED
        ]
        if not any(item.enabled_for_production for item in discovery.report_type_assessments):
            raise ValueError("semantic version must enable at least one report type")
        return SemanticVersion(
            version=version,
            report_types=discovery.report_type_assessments,
            predicates=accepted_predicates,
            concepts=accepted_concepts,
            assertion_types=[
                "OBSERVED_FACT",
                "COMPANY_DISCLOSURE",
                "MANAGEMENT_PLAN",
                "ANALYST_ESTIMATE",
                "ANALYST_OPINION",
                "FORECAST",
                "SCENARIO_ASSUMPTION",
            ],
            metadata={
                "discovery_run_id": str(discovery.run_id),
                "published_at": datetime.now(UTC).isoformat(),
            },
        )

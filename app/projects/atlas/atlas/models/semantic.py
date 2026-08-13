from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from atlas.models.extraction import StrictModel
from atlas.models.taxonomy import CrosswalkRun


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ReportTypeAssessment(StrictModel):
    report_type: str
    sampled_document_count: int = Field(ge=0)
    readable_document_count: int = Field(ge=0)
    useful_document_count: int = Field(ge=0)
    useful_ratio: float = Field(ge=0, le=1)
    enabled_for_production: bool
    prompt_profile_key: str | None = None
    rationale: str

    @model_validator(mode="after")
    def enabled_requires_profile(self) -> "ReportTypeAssessment":
        if self.enabled_for_production and not self.prompt_profile_key:
            raise ValueError("enabled report type requires prompt_profile_key")
        return self


class PredicateProposal(StrictModel):
    proposal_id: UUID = Field(default_factory=uuid4)
    canonical_name: str
    display_name: str
    description: str
    subject_types: list[str]
    object_types: list[str]
    aliases: list[str] = Field(default_factory=list)
    inverse_predicate: str | None = None
    evidence_document_ids: list[str] = Field(default_factory=list)
    occurrence_count: int = Field(default=1, ge=1)
    status: ProposalStatus = ProposalStatus.PROPOSED


class ConceptProposal(StrictModel):
    proposal_id: UUID = Field(default_factory=uuid4)
    concept_type: str
    canonical_name: str
    display_name: str
    description: str
    aliases: list[str] = Field(default_factory=list)
    evidence_document_ids: list[str] = Field(default_factory=list)
    occurrence_count: int = Field(default=1, ge=1)
    status: ProposalStatus = ProposalStatus.PROPOSED


class DiscoveryDocumentResult(StrictModel):
    document_id: str
    report_type: str
    readable: bool
    useful_for_graph: bool
    usefulness_reason: str
    recommended_prompt_profile_key: str | None = None
    predicate_proposals: list[PredicateProposal] = Field(default_factory=list)
    concept_proposals: list[ConceptProposal] = Field(default_factory=list)
    sample_output_object_key: str | None = None


class DiscoveryRun(StrictModel):
    run_id: UUID = Field(default_factory=uuid4)
    requested_sample_size: int = Field(ge=0, le=10000)
    sampled_document_ids: list[str] = Field(default_factory=list)
    document_results: list[DiscoveryDocumentResult] = Field(default_factory=list)
    report_type_assessments: list[ReportTypeAssessment] = Field(default_factory=list)
    predicate_proposals: list[PredicateProposal] = Field(default_factory=list)
    concept_proposals: list[ConceptProposal] = Field(default_factory=list)
    status: str = "PROPOSED"


class SemanticVersion(StrictModel):
    version: str
    extraction_schema_version: str = "atlas-extraction-v2"
    report_types: list[ReportTypeAssessment]
    predicates: list[PredicateProposal]
    concepts: list[ConceptProposal]
    assertion_types: list[str]
    industry_crosswalks: list[CrosswalkRun] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def report_profile(self, report_type: str, *, allow_disabled: bool = False) -> dict[str, Any]:
        for item in self.report_types:
            if item.report_type == report_type:
                if not item.enabled_for_production and not allow_disabled:
                    raise ValueError(f"report type '{report_type}' is disabled")
                return item.model_dump(mode="json")
        raise KeyError(f"report type '{report_type}' is absent from semantic version")

    @property
    def enabled_report_types(self) -> list[str]:
        return [item.report_type for item in self.report_types if item.enabled_for_production]

    @property
    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class FieldRecommendation(StrictModel):
    """One field the summary agent recommends extracting for full production."""
    field_name: str
    description: str
    rationale: str
    occurrence_count: int = Field(default=1, ge=1)
    value_type: str = "text"
    unit: str | None = None
    support_document_count: int = Field(default=1, ge=1)
    applicable_document_count: int = Field(default=1, ge=1)
    support_ratio: float = Field(default=0, ge=0, le=1)
    example_values: list[str] = Field(default_factory=list)
    evidence_document_ids: list[str] = Field(default_factory=list)
    applicable_subtypes: list[str] = Field(default_factory=list)
    scope: str = "CORE"
    knowledge_graph_role: str = ""
    value_shape: str = ""
    applicability: str = ""
    observed_json_paths: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)


class CategoryFieldSummary(StrictModel):
    """7th-pass agent output: per-category recommended fields for full extraction."""
    report_type: str
    recommended_fields: list[FieldRecommendation] = Field(default_factory=list)
    recommended_prompt_profile_key: str | None = None
    notes: str = ""
    sampled_document_count: int = Field(default=0, ge=0)
    readable_document_count: int = Field(default=0, ge=0)
    core_fields: list[FieldRecommendation] = Field(default_factory=list)
    conditional_fields: list[FieldRecommendation] = Field(default_factory=list)
    rejected_over_specific_fields: list[dict[str, Any]] = Field(default_factory=list)
    document_type_insights: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    review_method: str = ""

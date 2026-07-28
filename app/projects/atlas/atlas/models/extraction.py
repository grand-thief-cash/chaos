from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Readability(StrEnum):
    READABLE = "READABLE"
    UNREADABLE = "UNREADABLE"


class EntityType(StrEnum):
    COMPANY = "COMPANY"
    PRODUCT = "PRODUCT"
    MATERIAL = "MATERIAL"
    TECHNOLOGY = "TECHNOLOGY"
    MARKET = "MARKET"
    INDUSTRY_CLASS = "INDUSTRY_CLASS"
    VALUE_CHAIN = "VALUE_CHAIN"
    ASSET = "ASSET"
    OTHER = "OTHER"


class AssertionType(StrEnum):
    OBSERVED_FACT = "OBSERVED_FACT"
    COMPANY_DISCLOSURE = "COMPANY_DISCLOSURE"
    MANAGEMENT_PLAN = "MANAGEMENT_PLAN"
    ANALYST_ESTIMATE = "ANALYST_ESTIMATE"
    ANALYST_OPINION = "ANALYST_OPINION"
    FORECAST = "FORECAST"
    SCENARIO_ASSUMPTION = "SCENARIO_ASSUMPTION"


class Polarity(StrEnum):
    AFFIRMED = "AFFIRMED"
    NEGATED = "NEGATED"
    UNCERTAIN = "UNCERTAIN"


class DocumentAssessment(StrictModel):
    readability: Readability
    readability_reason: str | None = None
    observed_title: str | None = None
    primary_language: str = "zh"
    possible_truncation: bool = False
    last_page_referenced: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def unreadable_requires_reason(self) -> "DocumentAssessment":
        if self.readability == Readability.UNREADABLE and not self.readability_reason:
            raise ValueError("readability_reason is required when PDF is unreadable")
        return self


class EntityMention(StrictModel):
    mention_id: str = Field(min_length=1, max_length=64)
    mention: str = Field(min_length=1, max_length=512)
    suggested_entity_type: EntityType
    country_hint: str | None = Field(default=None, max_length=16)
    ticker_hint: str | None = Field(default=None, max_length=64)
    context: str = Field(min_length=1, max_length=2000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    page_number: int | None = Field(default=None, ge=1)


class RelationClaimCandidate(StrictModel):
    candidate_id: str
    subject_mention_id: str
    subject_mention: str
    raw_predicate: str
    predicate_family: str
    canonical_predicate_hint: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_]{1,127}$",
    )
    object_mention_id: str
    object_mention: str
    assertion_type: AssertionType
    polarity: Polarity = Polarity.AFFIRMED
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    valid_from: date | str | None = None
    valid_to: date | str | None = None
    evidence_quote: str = Field(min_length=1, max_length=2000)
    page_number: int | None = Field(default=None, ge=1)
    extraction_confidence: float = Field(ge=0, le=1)


class QuantifiedClaimCandidate(StrictModel):
    candidate_id: str
    subject_mention_id: str
    subject_mention: str
    metric_raw_name: str
    metric_hint: str | None = None
    value: float | int | None = None
    value_text: str
    unit: str | None = None
    period: str | None = None
    change_type: str | None = None
    base_value: float | None = None
    target_value: float | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    assertion_type: AssertionType
    evidence_quote: str = Field(min_length=1, max_length=2000)
    page_number: int | None = Field(default=None, ge=1)
    extraction_confidence: float = Field(ge=0, le=1)


class AnalystViewCandidate(StrictModel):
    candidate_id: str
    subject_mention_id: str | None = None
    subject_mention: str | None = None
    view_type_hint: str | None = None
    stance: str | None = None
    summary: str = Field(min_length=1, max_length=2000)
    time_horizon: str | None = None
    assertion_type: AssertionType = AssertionType.ANALYST_OPINION
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence_quote: str = Field(min_length=1, max_length=2000)
    page_number: int | None = Field(default=None, ge=1)
    extraction_confidence: float = Field(ge=0, le=1)


class UnknownSemanticTerm(StrictModel):
    semantic_kind: str
    raw_term: str
    context: str
    page_number: int | None = Field(default=None, ge=1)


class ExtractionResult(StrictModel):
    schema_version: str
    semantic_version: str
    document_id: str
    document_assessment: DocumentAssessment
    entity_mentions: list[EntityMention]
    relation_claims: list[RelationClaimCandidate]
    quantified_claims: list[QuantifiedClaimCandidate]
    analyst_views: list[AnalystViewCandidate]
    unknown_semantic_terms: list[UnknownSemanticTerm]

    @model_validator(mode="after")
    def validate_references(self) -> "ExtractionResult":
        mentions = {m.mention_id for m in self.entity_mentions}
        if len(mentions) != len(self.entity_mentions):
            raise ValueError("entity mention ids must be unique")
        for claim in self.relation_claims:
            if claim.subject_mention_id not in mentions or claim.object_mention_id not in mentions:
                raise ValueError(f"relation {claim.candidate_id} references unknown mention")
        for claim in self.quantified_claims:
            if claim.subject_mention_id not in mentions:
                raise ValueError(f"quantified claim {claim.candidate_id} references unknown mention")
        for view in self.analyst_views:
            if view.subject_mention_id and view.subject_mention_id not in mentions:
                raise ValueError(f"analyst view {view.candidate_id} references unknown mention")
        return self


class ResearchReport(StrictModel):
    source: str
    resource_id: str
    report_type: str
    subject_id: int | None = None
    subject_source_code: str = ""
    publish_date: str
    title: str
    org_name: str
    pdf_object_key: str
    status: str
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def document_id(self) -> str:
        return f"{self.source}:{self.resource_id}"


class ExtractionRunStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    SUPERSEDED = "SUPERSEDED"


class ExtractionRun(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    source_document_id: str
    source_content_hash: str = ""
    source_report_type: str
    pipeline_version: str
    run_generation: int = 0
    input_mode: str = "PDF_DIRECT"
    pdf_size_bytes: int | None = None
    pdf_page_count: int | None = None
    pdf_unlock_status: str | None = None
    pdf_unlocker_version: str = "pikepdf-v1"
    model_id: str
    prompt_signature: str
    extraction_schema_version: str
    semantic_version: str
    status: ExtractionRunStatus = ExtractionRunStatus.PENDING
    error_code: str | None = None
    error_summary: str | None = None
    request_attempt_count: int = 0
    validation_error_codes: list[str] = Field(default_factory=list)
    possible_truncation: bool = False
    last_page_referenced: int | None = None
    relation_claim_count: int = 0
    quantified_claim_count: int = 0
    analyst_view_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None

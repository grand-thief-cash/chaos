from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from atlas.models.extraction import AssertionType, Polarity, StrictModel


class ResolutionState(StrEnum):
    RESOLVED_SECURITY = "RESOLVED_SECURITY"
    RESOLVED_KNOWLEDGE_ENTITY = "RESOLVED_KNOWLEDGE_ENTITY"
    PROVISIONAL = "PROVISIONAL"
    AMBIGUOUS = "AMBIGUOUS"


class KnowledgeEntity(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    canonical_name: str
    normalized_name: str
    entity_type: str
    country_code: str = ""
    resolution_state: ResolutionState
    attributes: dict[str, Any] = Field(default_factory=dict)


class KnowledgeEntityAlias(StrictModel):
    entity_id: UUID
    alias: str
    normalized_alias: str
    language: str = ""
    source: str = "REPORT_EXTRACTION"


class EntityCandidate(StrictModel):
    entity: KnowledgeEntity
    security_id: int | None = None
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class ResolvedMention(StrictModel):
    mention_id: str
    entity: KnowledgeEntity
    security_id: int | None = None
    confidence: float = Field(ge=0, le=1)
    method: str


class RelationClaim(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    source_document_id: str
    subject_entity_id: UUID
    object_entity_id: UUID
    canonical_predicate: str
    assertion_type: AssertionType
    polarity: Polarity = Polarity.AFFIRMED
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str
    page_number: int | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    status: str = "ACCEPTED"


class QuantifiedClaim(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    source_document_id: str
    subject_entity_id: UUID
    metric_raw_name: str
    metric_hint: str | None = None
    value: float | int | None = None
    value_text: str
    unit: str | None = None
    period: str | None = None
    change_type: str | None = None
    base_value: float | None = None
    target_value: float | None = None
    assertion_type: AssertionType
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str
    page_number: int | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    status: str = "ACCEPTED"


class AnalystView(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    source_document_id: str
    subject_entity_id: UUID | None = None
    view_type_hint: str | None = None
    stance: str | None = None
    summary: str
    time_horizon: str | None = None
    assertion_type: AssertionType = AssertionType.ANALYST_OPINION
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str
    page_number: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: str = "ACCEPTED"

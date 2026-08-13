from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.models.extraction import Readability


class FreeExtractionResult(BaseModel):
    """One document's model-authored JSON plus system-owned processing metadata.

    ``content`` deliberately has no business schema. Sampling needs the model to
    preserve the document's own structure and semantics before a separate
    cross-document review decides which extraction fields are reusable.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    document_id: str
    report_type: str
    observed_title: str | None = None
    document_subtype: str = "unknown"
    readability: Readability = Readability.READABLE
    readability_reason: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    covered_page_numbers: list[int] = Field(default_factory=list)
    source_page_count: int = Field(default=0, ge=0)
    chunk_count: int = Field(default=0, ge=0)
    coverage_truncated: bool = False
    quality_issues: list[str] = Field(default_factory=list)

    @property
    def readable(self) -> bool:
        return self.readability == Readability.READABLE and bool(self.content)


class GeneralFieldRecommendation(BaseModel):
    """A reusable full-extraction field proposed after reviewing documents."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    field_name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    scope: Literal["CORE", "CONDITIONAL"]
    knowledge_graph_role: str = Field(min_length=1, max_length=120)
    value_shape: str = Field(min_length=1, max_length=300)
    applicability: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=800)
    priority: int = Field(ge=1, le=5)
    source_document_ids: list[str] = Field(min_length=1)
    observed_json_paths: list[str] = Field(min_length=1, max_length=3)
    example_values: list[str] = Field(default_factory=list, max_length=2)

    @field_validator("field_name")
    @classmethod
    def field_name_must_be_schema_level(cls, value: str) -> str:
        if re.search(r"(?:19|20)\d{2}", value) or re.search(r"[_-]E$", value, re.I):
            raise ValueError("field_name must not contain a concrete period or _E suffix")
        return value


class RejectedSpecificField(BaseModel):
    """An observed key/fact intentionally excluded from the reusable schema."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    observed_field: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    generalized_to: str | None = Field(default=None, max_length=100)
    source_document_ids: list[str] = Field(min_length=1)


class CategoryFieldReview(BaseModel):
    """LLM review result for reusable cross-document extraction fields."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    report_type: str
    reviewed_document_count: int = Field(default=0, ge=0)
    core_fields: list[GeneralFieldRecommendation] = Field(default_factory=list, max_length=24)
    conditional_fields: list[GeneralFieldRecommendation] = Field(default_factory=list, max_length=30)
    rejected_over_specific_fields: list[RejectedSpecificField] = Field(
        default_factory=list, max_length=30
    )
    document_type_insights: list[str] = Field(default_factory=list, max_length=20)
    coverage_gaps: list[str] = Field(default_factory=list, max_length=20)
    review_notes: str = ""


class CatalogFieldProposal(BaseModel):
    """One cross-report-type field selected from reviewed category fields."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    field_name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    scope: Literal["CORE", "CONDITIONAL"]
    knowledge_graph_role: str = Field(min_length=1, max_length=120)
    value_shape: str = Field(min_length=1, max_length=300)
    applicability: str = Field(min_length=1, max_length=500)
    priority: int = Field(ge=1, le=5)
    source_field_ids: list[str] = Field(min_length=1, max_length=12)

    @field_validator("field_name")
    @classmethod
    def field_name_must_be_reusable(cls, value: str) -> str:
        if re.search(r"(?:19|20)\d{2}", value) or re.search(r"[_-]E$", value, re.I):
            raise ValueError("field_name must not contain a concrete period or _E suffix")
        return value


class SamplingFieldCatalogProposal(BaseModel):
    """LLM-authored final selection over already reviewed category fields."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    fields: list[CatalogFieldProposal] = Field(min_length=1, max_length=20)
    coverage_gaps: list[str] = Field(default_factory=list, max_length=12)
    review_notes: str = ""


class PredicateDiscovery(BaseModel):
    """One predicate the semantic summariser derives from free extractions."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    canonical_name: str
    display_name: str
    description: str = ""
    subject_types: list[str] = Field(default_factory=list)
    object_types: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    occurrence_count: int = 1


class ConceptDiscovery(BaseModel):
    """One concept the semantic summariser derives from free extractions."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    concept_type: str
    canonical_name: str
    display_name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    occurrence_count: int = 1


class CategoryDiscoverySummary(BaseModel):
    """Optional predicate/concept discovery output for one report type."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    report_type: str
    readability_summary: str = ""
    predicates: list[PredicateDiscovery] = Field(default_factory=list)
    concepts: list[ConceptDiscovery] = Field(default_factory=list)
    notes: str = ""

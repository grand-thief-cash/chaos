from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from atlas.models.extraction import StrictModel


class MappingRelation(StrEnum):
    EXACT = "EXACT"
    CLOSE = "CLOSE"
    BROADER = "BROADER"
    NARROWER = "NARROWER"
    RELATED = "RELATED"
    NO_CANONICAL_MAPPING = "NO_CANONICAL_MAPPING"


class TaxonomyNode(StrictModel):
    scheme: str
    code: str
    name: str
    level: int = Field(ge=1)
    parent_code: str | None = None
    description: str | None = None


class CrosswalkMapping(StrictModel):
    mapping_id: UUID = Field(default_factory=uuid4)
    source_scheme: str
    source_code: str
    target_scheme: str
    target_code: str | None = None
    relation: MappingRelation
    confidence: float = Field(ge=0, le=1)
    rationale: str
    exception_reason: str | None = None


class CrosswalkValidation(StrictModel):
    valid: bool
    source_count: int
    mapped_source_count: int
    coverage_ratio: float = Field(ge=0, le=1)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CrosswalkRun(StrictModel):
    run_id: UUID = Field(default_factory=uuid4)
    source_scheme: str
    target_scheme: str
    mappings: list[CrosswalkMapping]
    validation: CrosswalkValidation
    status: str

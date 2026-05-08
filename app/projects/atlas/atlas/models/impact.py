"""Impact analysis output models."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ImpactItem(BaseModel):
    """A single company's impact from an event."""
    company: str = ""
    ticker: str = ""
    direction: str = ""              # positive|negative|neutral
    impact_type: str = ""            # cost|revenue|demand|supply|valuation
    strength: str = ""               # high|medium|low
    strength_score: float = 0.0      # Numeric score for sorting
    transmission_path: str = ""      # Human-readable path description
    hop: int = 0                     # Distance from event source
    source: str = ""                 # direct|indirect


class ImpactResult(BaseModel):
    """Complete impact analysis output."""
    event_name: str = ""
    event_type: str = ""
    direct_impacts: list[ImpactItem] = Field(default_factory=list)
    indirect_impacts: list[ImpactItem] = Field(default_factory=list)
    total_affected: int = 0
    llm_analysis: str = ""           # LLM-generated analysis text (Markdown)


class CompanyReviewData(BaseModel):
    """Structured data for company review."""
    company_name: str = ""
    ticker: str = ""
    value_chain_position: str = ""
    industries: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    suppliers: list[str] = Field(default_factory=list)
    customers: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    resources: list[dict] = Field(default_factory=list)
    recent_events: list[dict] = Field(default_factory=list)
    risk_exposure: dict = Field(default_factory=dict)
    relationships_count: int = 0


class CompanyReview(BaseModel):
    """Company development review output."""
    company: str = ""
    review_text: str = ""            # LLM-generated review (Markdown)
    graph_data: CompanyReviewData = Field(default_factory=CompanyReviewData)


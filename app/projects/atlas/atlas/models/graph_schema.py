"""Pydantic models matching industry_extraction_skills.md JSON schema.

These models validate the structured output from LLM extraction and serve as
the canonical data contract between the extraction layer and the graph layer.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    EARNINGS = "earnings"
    RESEARCH = "research"
    NEWS = "news"
    ANNOUNCEMENT = "announcement"


class ValueChainPosition(str, Enum):
    UPSTREAM = "upstream"
    MIDSTREAM = "midstream"
    DOWNSTREAM = "downstream"
    UNKNOWN = "unknown"


class ImpactDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ImpactType(str, Enum):
    COST = "cost"
    REVENUE = "revenue"
    DEMAND = "demand"
    SUPPLY = "supply"
    VALUATION = "valuation"


class ImpactStrength(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResourceCategory(str, Enum):
    ENERGY = "energy"
    MINERAL = "mineral"
    COMPUTE = "compute"
    DATA = "data"


class Scarcity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Trend(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    UNKNOWN = "unknown"


class SupplyStatus(str, Enum):
    TIGHT = "tight"
    BALANCED = "balanced"
    OVERSUPPLY = "oversupply"
    UNKNOWN = "unknown"


class AssetType(str, Enum):
    FACTORY = "factory"
    PATENT = "patent"
    SUBSIDIARY = "subsidiary"
    MINE = "mine"
    BRAND = "brand"


class EventType(str, Enum):
    POLICY = "policy"
    EARNINGS = "earnings"
    ACCIDENT = "accident"
    MACRO = "macro"
    INDUSTRY = "industry"


class EventScope(str, Enum):
    GLOBAL = "global"
    INDUSTRY = "industry"
    COMPANY = "company"


class CompetitionType(str, Enum):
    DIRECT = "direct"
    SUBSTITUTE = "substitute"


# ── Source reference ───────────────────────────────────────────────────────────

class SourceRef(BaseModel):
    doc_id: str = ""
    section: str = ""
    text: str = ""


# ── Node models ────────────────────────────────────────────────────────────────

class CompanyNode(BaseModel):
    name: str
    normalized_name: str = ""
    ticker: str = ""
    country: str = ""
    roles: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class IndustryNode(BaseModel):
    name: str
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class MarketNode(BaseModel):
    name: str
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class ProductNode(BaseModel):
    name: str
    standard_name: str = ""
    category: str = ""
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class TechnologyNode(BaseModel):
    name: str
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class AssetNode(BaseModel):
    name: str
    type: AssetType = AssetType.FACTORY
    owner: str = ""
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class ResourceNode(BaseModel):
    name: str
    category: ResourceCategory = ResourceCategory.ENERGY
    unit: str = ""
    scarcity: Scarcity = Scarcity.UNKNOWN
    price_trend: Trend = Trend.UNKNOWN
    supply_status: SupplyStatus = SupplyStatus.UNKNOWN
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class PolicyNode(BaseModel):
    name: str
    type: str = ""
    impact_scope: EventScope = EventScope.INDUSTRY
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


class EventNode(BaseModel):
    name: str
    type: EventType = EventType.INDUSTRY
    impact_scope: EventScope = EventScope.INDUSTRY
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""


# ── Edge model ─────────────────────────────────────────────────────────────────

class EdgeAttributes(BaseModel):
    value_chain_position: ValueChainPosition = ValueChainPosition.UNKNOWN
    impact_direction: Optional[ImpactDirection] = None
    impact_type: Optional[ImpactType] = None
    impact_strength: Optional[ImpactStrength] = None
    transmission_path: str = ""
    competition_type: Optional[CompetitionType] = None
    product: str = ""
    dimension: str = ""
    notes: str = ""


class Edge(BaseModel):
    type: str  # e.g. "belongs_to_industry", "supplier_of", "impact_on"
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    attributes: EdgeAttributes = Field(default_factory=EdgeAttributes)
    is_inferred: bool = False
    confidence: float = 0.0
    time: str = ""
    source: SourceRef = Field(default_factory=SourceRef)
    evidence: str = ""

    model_config = {"populate_by_name": True}


# ── Nodes container ───────────────────────────────────────────────────────────

class Nodes(BaseModel):
    companies: list[CompanyNode] = Field(default_factory=list)
    industries: list[IndustryNode] = Field(default_factory=list)
    markets: list[MarketNode] = Field(default_factory=list)
    products: list[ProductNode] = Field(default_factory=list)
    technologies: list[TechnologyNode] = Field(default_factory=list)
    assets: list[AssetNode] = Field(default_factory=list)
    resources: list[ResourceNode] = Field(default_factory=list)
    policies: list[PolicyNode] = Field(default_factory=list)
    events: list[EventNode] = Field(default_factory=list)


# ── Top-level extraction result ────────────────────────────────────────────────

class ExtractionMeta(BaseModel):
    doc_id: str = ""
    source_type: SourceType = SourceType.NEWS
    company_name: str = ""
    time: str = ""
    parser_version: str = "v5"


class ExtractionResult(BaseModel):
    """Root model — the complete JSON output from LLM extraction."""
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)
    nodes: Nodes = Field(default_factory=Nodes)
    edges: list[Edge] = Field(default_factory=list)


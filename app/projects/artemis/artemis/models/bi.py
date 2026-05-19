from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


DisplayKind = Literal["amount", "ratio", "pct_point", "count"]
WarningSeverity = Literal["low", "medium", "high"]


class BIIndustryMeta(BaseModel):
    taxonomy: str = ""
    level: int = 0
    code: str = ""
    name: str = ""
    index_code: str = ""


class BICompanyMeta(BaseModel):
    symbol: str
    name: str = ""
    market: str = "zh_a"
    exchange: str = ""
    industry: BIIndustryMeta = Field(default_factory=BIIndustryMeta)
    comp_type_code: int = 0
    financial_sector: bool = False


class BISecuritySearchItem(BaseModel):
    symbol: str
    name: str = ""
    exchange: str = ""
    market: str = "zh_a"
    asset_type: str = "stock"
    status: str = ""


class BISecuritySearchResponse(BaseModel):
    query: str
    market: str = "zh_a"
    total: int = 0
    items: List[BISecuritySearchItem] = Field(default_factory=list)


class BIMetricValue(BaseModel):
    code: str
    label: str
    unit: str
    display_kind: DisplayKind
    value: Optional[float] = None
    same_period_last_year: Optional[float] = None
    yoy_delta: Optional[float] = None
    yoy_growth: Optional[float] = None
    data_period: str = ""
    source_fields: List[str] = Field(default_factory=list)
    available: bool = True
    degraded: bool = False
    notes: List[str] = Field(default_factory=list)


class BITrendSeries(BaseModel):
    code: str
    label: str
    values: List[Optional[float]] = Field(default_factory=list)


class BITrendSection(BaseModel):
    code: str
    title: str
    periods: List[str] = Field(default_factory=list)
    series: List[BITrendSeries] = Field(default_factory=list)


class BISummaryCard(BaseModel):
    code: str
    title: str
    items: List[BIMetricValue] = Field(default_factory=list)


class BIWarning(BaseModel):
    code: str
    severity: WarningSeverity
    title: str
    message: str
    evidence_metric_codes: List[str] = Field(default_factory=list)


class BISourceNote(BaseModel):
    section: str
    statement_types: List[str] = Field(default_factory=list)
    pit_rule: str = "ann_date_before"
    metric_version: str = "v1"


class BIDashboardResponse(BaseModel):
    symbol: str
    as_of_date: str
    latest_period: str = ""
    company: BICompanyMeta
    kpis: List[BIMetricValue] = Field(default_factory=list)
    trend_sections: List[BITrendSection] = Field(default_factory=list)
    summary_cards: List[BISummaryCard] = Field(default_factory=list)
    warnings: List[BIWarning] = Field(default_factory=list)
    source_notes: List[BISourceNote] = Field(default_factory=list)


class BIDupontNode(BaseModel):
    code: str
    label: str
    metric: BIMetricValue
    children: List["BIDupontNode"] = Field(default_factory=list)


class BIDriverSummaryItem(BaseModel):
    driver: str
    direction: Literal["up", "down", "flat"]
    message: str


class BIDupontComparisonRow(BaseModel):
    period: str
    roe: Optional[float] = None
    net_margin: Optional[float] = None
    asset_turnover: Optional[float] = None
    equity_multiplier: Optional[float] = None


class BIDupontResponse(BaseModel):
    symbol: str
    as_of_date: str
    latest_period: str = ""
    company: BICompanyMeta
    headline_metrics: Dict[str, BIMetricValue] = Field(default_factory=dict)
    dupont_tree: BIDupontNode
    trend_sections: List[BITrendSection] = Field(default_factory=list)
    driver_summary: List[BIDriverSummaryItem] = Field(default_factory=list)
    comparison_rows: List[BIDupontComparisonRow] = Field(default_factory=list)


class BIQualityTableRow(BaseModel):
    period: str
    values: Dict[str, Optional[float]] = Field(default_factory=dict)


class BIQualityPanel(BaseModel):
    code: str
    title: str
    metrics: List[BIMetricValue] = Field(default_factory=list)
    trend_sections: List[BITrendSection] = Field(default_factory=list)
    table_rows: List[BIQualityTableRow] = Field(default_factory=list)
    warnings: List[BIWarning] = Field(default_factory=list)


class BIQualityResponse(BaseModel):
    symbol: str
    as_of_date: str
    latest_period: str = ""
    company: BICompanyMeta
    panels: List[BIQualityPanel] = Field(default_factory=list)
    source_notes: List[BISourceNote] = Field(default_factory=list)


class BIPeerComparisonRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)
    industry_code: str = ""
    as_of_date: str
    market: str = "zh_a"
    source: str = "amazing_data"
    metrics: List[str] = Field(default_factory=list)
    limit: int = 10


class BIPeerComparisonRow(BaseModel):
    symbol: str
    company_name: str = ""
    industry_name: str = ""
    metrics: Dict[str, BIMetricValue] = Field(default_factory=dict)


class BIPeerComparisonResponse(BaseModel):
    as_of_date: str
    market: str = "zh_a"
    industry_code: str = ""
    requested_metrics: List[str] = Field(default_factory=list)
    rows: List[BIPeerComparisonRow] = Field(default_factory=list)


class BIInsightHighlight(BaseModel):
    code: str
    title: str
    message: str
    related_metrics: List[str] = Field(default_factory=list)


class BIInsightResponse(BaseModel):
    symbol: str
    as_of_date: str
    latest_period: str = ""
    company: BICompanyMeta
    headline: str = ""
    structured_highlights: List[BIInsightHighlight] = Field(default_factory=list)
    anomalies: List[BIWarning] = Field(default_factory=list)
    trend_summary: List[str] = Field(default_factory=list)
    source_notes: List[BISourceNote] = Field(default_factory=list)


class BIMetricDefinition(BaseModel):
    code: str
    label: str
    category: str
    display_kind: DisplayKind
    unit: str
    formula: str
    source_fields: List[str] = Field(default_factory=list)
    applicable_comp_types: List[int] = Field(default_factory=list)
    phase: str = "phase1"
    available: bool = True


class BIMetricsMetaResponse(BaseModel):
    version: str = "v1"
    metrics: List[BIMetricDefinition] = Field(default_factory=list)


BIDupontNode.model_rebuild()




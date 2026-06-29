"""Lightweight BI models for the redesigned BI layer.

The old BI layer (dashboard/dupont/quality/insight/peer-comparison/metrics) was
dropped. This new layer is a thin wrapper over phoenixA raw data APIs, with
optional 同比(YoY) / 环比(QoQ) computation done in artemis.

Design principle: phoenixA is a data middle-platform (no business computation).
artemis is the lightweight BI layer that does aggregation/comparison. cthulhu
calls artemis /bi/* endpoints.
"""
from __future__ import annotations

from typing import Any, List, Optional, Literal

from pydantic import BaseModel


class BISecuritiesResponse(BaseModel):
    """Paginated securities list — passthrough from phoenixA /api/v2/securities."""
    items: List[dict]
    total: int
    limit: int
    offset: int


class BIRawQueryResponse(BaseModel):
    """Flat raw query response — passthrough from phoenixA flat format.

    For mode=yoy/qoq, rows carry extra *_yoy_delta / *_yoy_growth /
    *_qoq_delta / *_qoq_growth keys computed by artemis.
    """
    generated_at: str
    dataset: str
    source: str
    data_type: str
    rows: List[dict]
    fields: List[dict]
    total: int
    page: int
    page_size: int
    mode: str = "raw"


# ─── DuPont analysis ───
#
# DuPont decomposition tree computed by artemis from raw income +
# balance_sheet statements fetched from phoenixA. artemis owns the
# business computation (ratios, averages, period-over-period deltas);
# cthulhu only renders the structured result.


class BIDupontMetricNode(BaseModel):
    """One node in the DuPont decomposition tree.

    `value` is the raw numeric value (ratio for rates, yuan for amounts).
    `prev_value` is the prior-period value used to derive `delta` and
    `direction`. Formatting to "%" / "亿元" / "+Xpct" happens in the
    frontend; artemis returns raw numbers + unit hints.
    """
    code: str
    label: str
    value: Optional[float] = None
    prev_value: Optional[float] = None
    delta: Optional[float] = None
    direction: Optional[str] = None  # 'up' | 'down' | 'flat' | None
    unit: str = "ratio"  # 'ratio' | 'amount_yuan'
    available: bool = True
    note: Optional[str] = None


class BIDupontTreeNode(BIDupontMetricNode):
    """A metric node that also carries its decomposition children."""
    children: List["BIDupontTreeNode"] = []


class BIDriverItem(BaseModel):
    label: str
    value: Optional[float] = None
    prev_value: Optional[float] = None
    note: str
    direction: Optional[str] = None
    unit: str = "ratio"


class BIDetailEquation(BaseModel):
    result_label: str
    result_value: Optional[float] = None
    expression: str
    note: str
    unit: str = "amount_yuan"


class BIDetailStackRow(BaseModel):
    label: str
    raw_field: str
    value: Optional[float] = None


class BIDetailStack(BaseModel):
    title: str
    total: Optional[float] = None
    accent: str
    rows: List[BIDetailStackRow]


class BIDupontResponse(BaseModel):
    """Full DuPont analysis result for one symbol/period."""
    generated_at: str
    symbol: str
    source: str
    market: str
    report_type: str
    statement_code: str
    period: str  # current reporting_period (YYYY-MM-DD)
    prev_period: Optional[str] = None
    security_name: Optional[str] = None
    # New: period kind
    period_kind: Literal["annual", "single_quarter", "ytd", "ttm"]
    target_reporting_period: str
    # New: Q4 extrapolation result
    extrapolated_full_year: Optional["BIDupontResponse"] = None
    # Headline strip
    headline_drivers: List[BIDriverItem]
    # Decomposition tree (ROE → {net_margin, asset_turnover, equity_multiplier} → leaves)
    tree: BIDupontTreeNode
    # Flat node map keyed by code, for the canvas layout
    nodes: dict
    # Relationship equations
    detail_equations: List[BIDetailEquation]
    # Breakdown stacks
    detail_stacks: List[BIDetailStack]
    notes: List[str] = []


BIDupontTreeNode.model_rebuild()
BIDupontResponse.model_rebuild()

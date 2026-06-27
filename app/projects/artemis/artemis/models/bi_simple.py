"""Lightweight BI models for the redesigned BI layer.

The old BI layer (dashboard/dupont/quality/insight/peer-comparison/metrics) was
dropped. This new layer is a thin wrapper over phoenixA raw data APIs, with
optional 同比(YoY) / 环比(QoQ) computation done in artemis.

Design principle: phoenixA is a data middle-platform (no business computation).
artemis is the lightweight BI layer that does aggregation/comparison. cthulhu
calls artemis /bi/* endpoints.
"""
from __future__ import annotations

from typing import Any, List, Optional

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

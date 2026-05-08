"""Event models — fingerprint, dedup, and event type definitions."""
from __future__ import annotations

import hashlib
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field


class EventFingerprint(BaseModel):
    """Structured event identity for deduplication (Layer 2)."""
    entity: str          # Affected entity (normalized)
    event_type: str      # From taxonomy event_types
    direction: str       # up|down|neutral|new|removed
    time_bucket: str     # 2026-W19 / 2026-05 / 2026-Q2

    @property
    def fingerprint(self) -> str:
        """Generate a deterministic hash from the event identity."""
        raw = f"{self.entity}|{self.event_type}|{self.direction}|{self.time_bucket}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class KgEvent(BaseModel):
    """Full event record for persistence."""
    id: int = 0
    event_fingerprint: str = ""
    entity_name: str = ""
    event_type: str = ""
    direction: str = ""
    time_bucket: str = ""
    description: str = ""
    severity: str = "medium"  # high|medium|low
    source_doc_ids: list[str] = Field(default_factory=list)
    source_count: int = 1
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    impact_triggered: bool = False


class EventDedupResult(BaseModel):
    """Result of an event dedup check."""
    is_new: bool = True
    event: KgEvent = Field(default_factory=KgEvent)
    merged_sources: int = 0  # Number of existing sources merged


# ── Time bucket helpers ────────────────────────────────────────────────────

# Event type → time bucket granularity mapping (per design doc §3.4)
_TIME_BUCKET_GRANULARITY: dict[str, str] = {
    "price_change": "week",
    "supply_change": "week",
    "policy_new": "month",
    "policy_change": "month",
    "tariff_change": "month",
    "tech_breakthrough": "week",
    "capacity_change": "week",
    "merger_acquisition": "month",
    "investment": "month",
    "leadership_change": "week",
    "earnings_beat": "quarter",
    "earnings_miss": "quarter",
    "accident_disaster": "day",
    "sanction": "month",
    "other": "week",  # default
}


def compute_time_bucket(event_type: str, dt: date | None = None) -> str:
    """Compute time bucket string based on event type and date.

    Returns formats like: 2026-W19, 2026-05, 2026-Q2, 2026-05-08
    """
    if dt is None:
        dt = date.today()

    granularity = _TIME_BUCKET_GRANULARITY.get(event_type, "week")

    if granularity == "day":
        return dt.isoformat()  # 2026-05-08
    elif granularity == "week":
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"  # 2026-W19
    elif granularity == "month":
        return f"{dt.year}-{dt.month:02d}"  # 2026-05
    elif granularity == "quarter":
        quarter = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{quarter}"  # 2026-Q2
    else:
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"


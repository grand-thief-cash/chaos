"""Event dedup service — fingerprint generation + dedup check via phoenixA."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from atlas.connectors import phoenixa_client
from atlas.models.event import EventFingerprint, KgEvent, EventDedupResult, compute_time_bucket

logger = logging.getLogger(__name__)


async def dedup_event(
    entity_name: str,
    event_type: str,
    direction: str,
    description: str = "",
    severity: str = "medium",
    source_doc_id: str = "",
    event_date: date | None = None,
) -> EventDedupResult:
    """Check if an event already exists; create or merge accordingly.

    Returns EventDedupResult indicating whether this is a new event.
    """
    time_bucket = compute_time_bucket(event_type, event_date)

    fp = EventFingerprint(
        entity=entity_name,
        event_type=event_type,
        direction=direction,
        time_bucket=time_bucket,
    )
    fingerprint = fp.fingerprint

    # Check if event with same fingerprint exists
    existing_events = await phoenixa_client.list_events(fingerprint=fingerprint, limit=1)

    if existing_events:
        # Event exists — merge source
        existing = existing_events[0]
        existing_sources = existing.get("source_doc_ids", []) or []
        if source_doc_id and source_doc_id not in existing_sources:
            existing_sources.append(source_doc_id)

        updates: dict[str, Any] = {
            "source_doc_ids": existing_sources,
            "source_count": len(existing_sources),
            "last_seen_at": date.today().isoformat() + "T00:00:00",
        }
        # Update description if new one is longer/better
        if description and len(description) > len(existing.get("description", "")):
            updates["description"] = description

        event_id = existing.get("id", 0)
        await phoenixa_client.update_event(event_id, updates)

        logger.info(
            "Event deduped: fingerprint=%s entity=%s type=%s (source_count=%d)",
            fingerprint[:12], entity_name, event_type, len(existing_sources),
        )
        return EventDedupResult(
            is_new=False,
            event=KgEvent(
                id=event_id,
                event_fingerprint=fingerprint,
                entity_name=entity_name,
                event_type=event_type,
                direction=direction,
                time_bucket=time_bucket,
                description=existing.get("description", description),
                severity=existing.get("severity", severity),
                source_doc_ids=existing_sources,
                source_count=len(existing_sources),
                impact_triggered=existing.get("impact_triggered", False),
            ),
            merged_sources=1,
        )
    else:
        # New event — create
        source_doc_ids = [source_doc_id] if source_doc_id else []
        event_data = {
            "event_fingerprint": fingerprint,
            "entity_name": entity_name,
            "event_type": event_type,
            "direction": direction,
            "time_bucket": time_bucket,
            "description": description,
            "severity": severity,
            "source_doc_ids": source_doc_ids,
            "source_count": len(source_doc_ids),
            "impact_triggered": False,
        }
        created = await phoenixa_client.create_event(event_data)

        logger.info(
            "New event created: fingerprint=%s entity=%s type=%s",
            fingerprint[:12], entity_name, event_type,
        )
        return EventDedupResult(
            is_new=True,
            event=KgEvent(
                id=created.get("id", 0),
                event_fingerprint=fingerprint,
                entity_name=entity_name,
                event_type=event_type,
                direction=direction,
                time_bucket=time_bucket,
                description=description,
                severity=severity,
                source_doc_ids=source_doc_ids,
                source_count=len(source_doc_ids),
            ),
        )


async def mark_impact_triggered(event_id: int) -> None:
    """Mark an event as having triggered the Impact Engine."""
    await phoenixa_client.update_event(event_id, {"impact_triggered": True})


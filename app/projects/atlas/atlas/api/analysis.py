"""Impact analysis & company review & events endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from atlas.connectors import phoenixa_client
from atlas.services.impact import (
    analyze_event_impact,
    analyze_company_exposure,
)
from atlas.services.company_review import generate_company_review

router = APIRouter()


@router.get("/event/{event_name}/impact")
async def event_impact(event_name: str, max_hops: int = 3):
    """Analyze the impact of an event on companies."""
    result = await analyze_event_impact(event_name, max_hops=max_hops)
    return result


@router.get("/company/{name}/exposure")
async def company_exposure(name: str):
    """Get a company's risk exposure."""
    result = await analyze_company_exposure(name)
    return result


@router.get("/company/{name}/review")
async def company_review(name: str):
    """Generate an investment-oriented company development review."""
    result = await generate_company_review(name)
    return result.model_dump()


# ── Events (via phoenixA) ──────────────────────────────────────────────────

@router.get("/events/recent")
async def recent_events(days: int = Query(7, ge=1, le=90), limit: int = Query(50, le=200)):
    """Get recent events (deduplicated)."""
    events = await phoenixa_client.list_recent_events(days=days, limit=limit)
    return {"events": events, "total": len(events)}


@router.get("/events")
async def list_events(
    event_type: str = "",
    entity_name: str = "",
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """List all events with optional filters."""
    events = await phoenixa_client.list_events(
        event_type=event_type, entity_name=entity_name, limit=limit, offset=offset,
    )
    return {"events": events, "total": len(events)}


@router.get("/impact-logs")
async def list_impact_logs(
    event_name: str = "",
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """List impact analysis logs."""
    logs = await phoenixa_client.list_impact_logs(
        event_name=event_name, limit=limit, offset=offset,
    )
    return {"logs": logs, "total": len(logs)}


@router.get("/daily-runs")
async def list_daily_runs(limit: int = Query(30, le=100), offset: int = 0):
    """List daily pipeline runs."""
    runs = await phoenixa_client.list_daily_runs(limit=limit, offset=offset)
    return {"runs": runs, "total": len(runs)}


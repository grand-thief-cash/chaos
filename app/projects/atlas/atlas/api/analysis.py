"""Impact analysis & company review endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from atlas.services.impact import (
    analyze_event_impact,
    analyze_company_exposure,
    generate_company_review,
)

router = APIRouter()


@router.get("/event/{event_name}/impact")
async def event_impact(event_name: str, max_hops: int = 3):
    """Analyze the impact of an event on companies (graph traversal + LLM reasoning)."""
    result = await analyze_event_impact(event_name, max_hops=max_hops)
    return result


@router.get("/company/{name}/exposure")
async def company_exposure(name: str):
    """Get a company's risk exposure (events, resources, policies)."""
    result = await analyze_company_exposure(name)
    return result


@router.get("/company/{name}/review")
async def company_review(name: str):
    """Generate an investment-oriented company development review."""
    result = await generate_company_review(name)
    return result


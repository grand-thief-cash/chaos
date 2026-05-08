"""Graph query endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from atlas.services.graph_query import (
    get_company_full, get_company_chain, get_company_timeline,
    get_competitors, search_nodes, get_event_impacts, get_graph_stats,
)

router = APIRouter()


@router.get("/search")
async def search(q: str = Query(..., min_length=1), limit: int = Query(20, le=100)):
    """Full-text search across all entities."""
    results = await search_nodes(q, limit=limit)
    return {"query": q, "results": results, "total": len(results)}


@router.get("/stats")
async def graph_stats():
    """Get overall graph statistics."""
    return await get_graph_stats()


@router.get("/company/{name}")
async def get_company(name: str):
    """Get a company and all its direct relationships."""
    data = await get_company_full(name)
    if not data:
        return {"error": "Company not found", "company": name}
    return data


@router.get("/company/{name}/chain")
async def get_chain(name: str, max_hops: int = Query(3, ge=1, le=5)):
    """Get the industry chain around a company."""
    data = await get_company_chain(name, max_hops=max_hops)
    return {"company": name, "chain": data}


@router.get("/company/{name}/timeline")
async def get_timeline(name: str):
    """Get time-ordered events for a company."""
    data = await get_company_timeline(name)
    return {"company": name, "timeline": data}


@router.get("/company/{name}/competitors")
async def get_company_competitors(name: str):
    """Get competitors of a company."""
    data = await get_competitors(name)
    return {"company": name, "competitors": data}


@router.get("/event/{name}/impacts")
async def get_event_impact_list(name: str):
    """Get all companies impacted by an event."""
    data = await get_event_impacts(name)
    return {"event": name, "impacts": data}

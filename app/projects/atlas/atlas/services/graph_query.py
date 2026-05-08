"""Graph query service — read-only queries via PhoenixA's graph API."""
from __future__ import annotations

import logging
from typing import Any

from atlas.connectors import phoenixa_client

logger = logging.getLogger(__name__)


async def search_nodes(query: str, limit: int = 20) -> list[dict]:
    """Full-text search across all node names."""
    return await phoenixa_client.graph_search_nodes(query, limit=limit)


async def get_company_full(company_name: str) -> dict[str, Any]:
    """Get a company and all its direct relationships."""
    return await phoenixa_client.graph_get_company(company_name)


async def get_company_chain(company_name: str, max_hops: int = 3) -> dict:
    """Get the supply chain around a company."""
    return await phoenixa_client.graph_get_company_chain(company_name, max_hops=max_hops)


async def get_company_timeline(company_name: str) -> list[dict]:
    """Get time-ordered events for a company."""
    return await phoenixa_client.graph_get_company_timeline(company_name)


async def get_competitors(company_name: str) -> list[dict]:
    """Get competitors of a company."""
    return await phoenixa_client.graph_get_competitors(company_name)


async def get_event_impacts(event_name: str) -> list[dict]:
    """Find all companies impacted by an event."""
    return await phoenixa_client.graph_get_event_impacts(event_name)


async def get_resource_related_companies(resource_name: str) -> list[dict]:
    """Get companies related to a resource (for impact rules)."""
    cypher = """
    MATCH (r:Resource {name: $name})<-[rel]-(c:Company)
    RETURN c.normalized_name AS name, c.ticker AS ticker,
           type(rel) AS rel_type, rel.confidence AS confidence
    """
    return await phoenixa_client.run_cypher(cypher, {"name": resource_name})


async def get_graph_stats() -> dict:
    """Get overall graph statistics."""
    return await phoenixa_client.graph_get_stats()


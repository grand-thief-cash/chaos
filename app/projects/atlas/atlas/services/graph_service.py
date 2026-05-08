"""Graph service — compatibility module.

Core logic has been moved to:
- graph_query.py — read-only queries via PhoenixA graph API
- graph_builder.py — entity resolution, quality gate, MERGE via PhoenixA
"""
from __future__ import annotations

# Re-export from new modules for backward compatibility
from atlas.services.graph_query import (
    get_company_full,
    get_company_chain,
    get_company_timeline,
    get_competitors,
    search_nodes,
    get_event_impacts,
)
from atlas.services.graph_builder import build_graph_from_extraction


async def ingest_extraction_result(result) -> dict[str, int]:
    """Write a full ExtractionResult into Neo4j via PhoenixA (legacy compatibility wrapper)."""
    counts = await build_graph_from_extraction(result)
    return {"nodes": counts["nodes_created"], "edges": counts["edges_created"]}

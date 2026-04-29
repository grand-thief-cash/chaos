"""Graph service — write / merge / query entities & edges in Neo4j."""
from __future__ import annotations

import logging
from typing import Any

from atlas.connectors.neo4j_client import get_session
from atlas.models.graph_schema import (
    ExtractionResult, Edge, CompanyNode, ProductNode, IndustryNode,
    ResourceNode, TechnologyNode, AssetNode, EventNode, PolicyNode, MarketNode,
)

logger = logging.getLogger(__name__)

# ── Label mapping ──────────────────────────────────────────────────────────────

_LABEL_MAP: dict[str, str] = {
    "companies": "Company",
    "industries": "Industry",
    "markets": "Market",
    "products": "Product",
    "technologies": "Technology",
    "assets": "Asset",
    "resources": "Resource",
    "policies": "Policy",
    "events": "Event",
}

# The key used for MERGE matching per label
_MERGE_KEY: dict[str, str] = {
    "Company": "normalized_name",
    "Industry": "name",
    "Market": "name",
    "Product": "name",
    "Technology": "name",
    "Asset": "name",
    "Resource": "name",
    "Policy": "name",
    "Event": "name",
}

# Relationship type mapping (skill edge type → Neo4j rel type)
_REL_TYPE_MAP: dict[str, str] = {
    "belongs_to_industry": "BELONGS_TO_INDUSTRY",
    "operates_in_market": "OPERATES_IN_MARKET",
    "produces": "PRODUCES",
    "uses_technology": "USES_TECHNOLOGY",
    "owns_asset": "OWNS_ASSET",
    "subsidiary_of": "SUBSIDIARY_OF",
    "invested_in": "INVESTED_IN",
    "supplier_of": "SUPPLIER_OF",
    "customer_of": "CUSTOMER_OF",
    "competitor_of": "COMPETITOR_OF",
    "applied_in": "APPLIED_IN",
    "involved_in_event": "INVOLVED_IN_EVENT",
    "impacted_by_policy": "IMPACTED_BY_POLICY",
    "part_of_product": "PART_OF_PRODUCT",
    "impact_on": "IMPACT_ON",
    "depends_on_resource": "DEPENDS_ON_RESOURCE",
    "consumes_resource": "CONSUMES_RESOURCE",
    "produces_resource": "PRODUCES_RESOURCE",
    "extracts_resource": "EXTRACTS_RESOURCE",
}


# ── Node writing ───────────────────────────────────────────────────────────────

def _node_props(node: Any) -> dict[str, Any]:
    """Convert a Pydantic node to a flat dict, serializing nested objects."""
    d = node.model_dump(exclude_none=True)
    # Flatten source to source_doc_id / source_section / source_text
    src = d.pop("source", {})
    if src:
        d["source_doc_id"] = src.get("doc_id", "")
        d["source_section"] = src.get("section", "")
        d["source_text"] = src.get("text", "")
    # Convert list fields to JSON strings for Neo4j
    for k, v in list(d.items()):
        if isinstance(v, list):
            import json
            d[k] = json.dumps(v, ensure_ascii=False)
    return d


def upsert_nodes(result: ExtractionResult) -> int:
    """MERGE all nodes from an ExtractionResult into Neo4j. Returns count."""
    count = 0
    with get_session() as session:
        for field_name, label in _LABEL_MAP.items():
            nodes = getattr(result.nodes, field_name, [])
            merge_key = _MERGE_KEY[label]
            for node in nodes:
                props = _node_props(node)
                merge_val = props.get(merge_key, props.get("name", ""))
                if not merge_val:
                    continue
                # MERGE on the unique key, SET all other properties
                cypher = (
                    f"MERGE (n:{label} {{{merge_key}: $merge_val}}) "
                    f"SET n += $props"
                )
                session.run(cypher, merge_val=merge_val, props=props)
                count += 1
    logger.info("Upserted %d nodes", count)
    return count


# ── Edge writing ───────────────────────────────────────────────────────────────

def _resolve_label(name: str, result: ExtractionResult) -> str | None:
    """Try to figure out the Neo4j label for a node name from the result."""
    for field_name, label in _LABEL_MAP.items():
        nodes = getattr(result.nodes, field_name, [])
        for node in nodes:
            n = getattr(node, "normalized_name", None) or getattr(node, "name", "")
            if n == name:
                return label
    return None


def upsert_edges(result: ExtractionResult) -> int:
    """MERGE all edges from an ExtractionResult into Neo4j. Returns count."""
    count = 0
    with get_session() as session:
        for edge in result.edges:
            rel_type = _REL_TYPE_MAP.get(edge.type, edge.type.upper())
            from_label = _resolve_label(edge.from_node, result) or "Company"
            to_label = _resolve_label(edge.to_node, result) or "Company"
            from_key = _MERGE_KEY.get(from_label, "name")
            to_key = _MERGE_KEY.get(to_label, "name")

            attrs = edge.attributes.model_dump(exclude_none=True)
            attrs["confidence"] = edge.confidence
            attrs["time"] = edge.time
            attrs["evidence"] = edge.evidence
            attrs["is_inferred"] = edge.is_inferred
            src = edge.source.model_dump() if edge.source else {}
            attrs["source_doc_id"] = src.get("doc_id", "")

            cypher = (
                f"MATCH (a:{from_label} {{{from_key}: $from_val}}) "
                f"MATCH (b:{to_label} {{{to_key}: $to_val}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r += $attrs"
            )
            session.run(
                cypher,
                from_val=edge.from_node,
                to_val=edge.to_node,
                attrs=attrs,
            )
            count += 1
    logger.info("Upserted %d edges", count)
    return count


def ingest_extraction_result(result: ExtractionResult) -> dict[str, int]:
    """Write a full ExtractionResult (nodes + edges) into Neo4j."""
    n = upsert_nodes(result)
    e = upsert_edges(result)
    return {"nodes": n, "edges": e}


# ── Query helpers ──────────────────────────────────────────────────────────────

def get_company_chain(company_name: str, max_hops: int = 3) -> list[dict]:
    """Get the full industry chain around a company (up to max_hops)."""
    cypher = """
    MATCH path = (c:Company {normalized_name: $name})-[*1..$hops]-(n)
    RETURN path
    LIMIT 200
    """
    with get_session() as session:
        records = session.run(cypher, name=company_name, hops=max_hops).data()
    return records


def get_company_full(company_name: str) -> dict[str, Any]:
    """Get a company and all its direct relationships."""
    cypher = """
    MATCH (c:Company {normalized_name: $name})
    OPTIONAL MATCH (c)-[r]-(n)
    RETURN c, collect(DISTINCT {rel_type: type(r), direction: CASE
        WHEN startNode(r) = c THEN 'outgoing' ELSE 'incoming' END,
        props: properties(r), neighbor: properties(n), neighbor_label: labels(n)[0]
    }) AS relationships
    """
    with get_session() as session:
        result = session.run(cypher, name=company_name).single()
    if result is None:
        return {}
    return {
        "company": dict(result["c"]),
        "relationships": result["relationships"],
    }


def get_event_impacts(event_name: str) -> list[dict]:
    """Find all companies impacted by an event."""
    cypher = """
    MATCH (e:Event {name: $name})-[r:IMPACT_ON]->(c:Company)
    RETURN c.normalized_name AS company, c.ticker AS ticker,
           r.impact_direction AS direction, r.impact_type AS type,
           r.impact_strength AS strength, r.transmission_path AS path
    ORDER BY r.impact_strength DESC
    """
    with get_session() as session:
        return session.run(cypher, name=event_name).data()


def search_nodes(query: str, limit: int = 20) -> list[dict]:
    """Full-text search across all node names."""
    cypher = """
    CALL {
        MATCH (n) WHERE n.name CONTAINS $q RETURN n, labels(n)[0] AS label
        UNION
        MATCH (n:Company) WHERE n.normalized_name CONTAINS $q RETURN n, 'Company' AS label
    }
    RETURN DISTINCT properties(n) AS props, label
    LIMIT $limit
    """
    with get_session() as session:
        return session.run(cypher, q=query, limit=limit).data()


def get_company_timeline(company_name: str) -> list[dict]:
    """Get time-ordered events/edges for a company."""
    cypher = """
    MATCH (c:Company {normalized_name: $name})-[r]-(n)
    WHERE r.time IS NOT NULL AND r.time <> '' AND r.time <> 'unknown'
    RETURN type(r) AS rel_type, properties(r) AS rel_props,
           labels(n)[0] AS neighbor_label, n.name AS neighbor_name, r.time AS time
    ORDER BY r.time DESC
    """
    with get_session() as session:
        return session.run(cypher, name=company_name).data()


def get_competitors(company_name: str) -> list[dict]:
    """Get competitors of a company."""
    cypher = """
    MATCH (c:Company {normalized_name: $name})-[r:COMPETITOR_OF]-(comp:Company)
    RETURN comp.normalized_name AS competitor, comp.ticker AS ticker,
           r.product AS product, r.competition_type AS competition_type,
           r.dimension AS dimension
    """
    with get_session() as session:
        return session.run(cypher, name=company_name).data()


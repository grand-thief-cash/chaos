"""Graph Builder — Entity resolution, quality gate, MERGE into Neo4j via PhoenixA.

Per design doc §5.1: Don't write raw extraction results to graph directly.
Graph Builder does dedup/standardize/quality-filter before writing.
All Neo4j writes go through PhoenixA's /api/v1/graph/* endpoints.
"""
from __future__ import annotations

import logging
from typing import Any

from atlas.connectors import phoenixa_client
from atlas.core.config import get_config
from atlas.models.graph_schema import ExtractionResult

logger = logging.getLogger(__name__)

# Label → merge key mapping
_MERGE_KEY = {
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

_LABEL_MAP = {
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

_REL_TYPE_MAP = {
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
    "other": "OTHER",
}


def _get_confidence_threshold() -> float:
    cfg = get_config()
    return cfg.get("graph", {}).get("low_confidence_threshold", 0.5)


# ── Quality Gate ───────────────────────────────────────────────────────────

def _passes_quality_gate(item: Any) -> bool:
    """Check if a node or edge meets quality requirements."""
    confidence = getattr(item, "confidence", 0.0)
    threshold = _get_confidence_threshold()
    if confidence < threshold:
        return False
    return True


# ── Node properties ────────────────────────────────────────────────────────

def _node_props(node: Any, doc_id: str = "") -> dict[str, Any]:
    """Convert a Pydantic node to flat dict for Neo4j."""
    d = node.model_dump(exclude_none=True)
    src = d.pop("source", {})
    d.pop("evidence", None)
    source_doc_id = src.get("doc_id", doc_id)
    if source_doc_id:
        d["source_doc_ids"] = [source_doc_id]
    # Convert list fields to strings for Neo4j
    for k, v in list(d.items()):
        if isinstance(v, list):
            import json
            d[k] = json.dumps(v, ensure_ascii=False)
    return d


# ── Main build function ───────────────────────────────────────────────────

async def build_graph_from_extraction(
    result: ExtractionResult,
    extraction_id: int = 0,
) -> dict[str, int]:
    """Process an ExtractionResult through quality gate and write to Neo4j via PhoenixA."""
    doc_id = result.meta.doc_id
    nodes_created = 0
    nodes_merged = 0
    edges_created = 0

    # ── Batch write nodes ──
    node_batch = []
    for field_name, label in _LABEL_MAP.items():
        nodes = getattr(result.nodes, field_name, [])
        merge_key = _MERGE_KEY[label]

        for node in nodes:
            if not _passes_quality_gate(node):
                logger.debug("Skipped low-quality node: %s (%s)", getattr(node, "name", "?"), label)
                continue

            props = _node_props(node, doc_id)
            merge_val = props.get(merge_key, props.get("name", ""))
            if not merge_val:
                continue

            node_batch.append({
                "label": label,
                "merge_key": merge_key,
                "merge_value": merge_val,
                "props": props,
            })

    if node_batch:
        try:
            resp = await phoenixa_client.merge_nodes_batch(node_batch)
            total = resp.get("total_affected", 0)
            nodes_created = len(node_batch)  # Approximate
            logger.debug("Merged %d nodes (affected=%d)", len(node_batch), total)
        except Exception as e:
            logger.error("Failed to merge node batch: %s", e)

    # ── Batch write edges ──
    edge_batch = []
    for edge in result.edges:
        if not _passes_quality_gate(edge):
            logger.debug("Skipped low-quality edge: %s->%s", edge.from_node, edge.to_node)
            continue

        rel_type = _REL_TYPE_MAP.get(edge.type, edge.type.upper())
        from_label = _resolve_label(edge.from_node, result) or "Company"
        to_label = _resolve_label(edge.to_node, result) or "Company"
        from_key = _MERGE_KEY.get(from_label, "name")
        to_key = _MERGE_KEY.get(to_label, "name")

        attrs = edge.attributes.model_dump(exclude_none=True)
        attrs["confidence"] = edge.confidence
        attrs["time"] = edge.time
        attrs["is_inferred"] = edge.is_inferred
        if doc_id:
            attrs["source_doc_ids"] = [doc_id]

        edge_batch.append({
            "from_label": from_label,
            "from_key": from_key,
            "from_value": edge.from_node,
            "to_label": to_label,
            "to_key": to_key,
            "to_value": edge.to_node,
            "rel_type": rel_type,
            "attrs": attrs,
        })

    if edge_batch:
        try:
            resp = await phoenixa_client.merge_edges_batch(edge_batch)
            edges_created = len(edge_batch)
            logger.debug("Merged %d edges", len(edge_batch))
        except Exception as e:
            logger.error("Failed to merge edge batch: %s", e)

    logger.info(
        "Graph build complete: doc=%s nodes=%d edges=%d",
        doc_id, nodes_created, edges_created,
    )

    # Record ingestion in phoenixA
    if extraction_id:
        try:
            await phoenixa_client.create_graph_ingestion({
                "extraction_id": extraction_id,
                "nodes_created": nodes_created,
                "edges_created": edges_created,
                "nodes_merged": nodes_merged,
            })
        except Exception as e:
            logger.warning("Failed to record graph ingestion: %s", e)

    return {
        "nodes_created": nodes_created,
        "edges_created": edges_created,
        "nodes_merged": nodes_merged,
    }


def _resolve_label(name: str, result: ExtractionResult) -> str | None:
    """Resolve Neo4j label for a node name from the extraction result."""
    for field_name, label in _LABEL_MAP.items():
        nodes = getattr(result.nodes, field_name, [])
        for node in nodes:
            n = getattr(node, "normalized_name", None) or getattr(node, "name", "")
            if n == name:
                return label
    return None


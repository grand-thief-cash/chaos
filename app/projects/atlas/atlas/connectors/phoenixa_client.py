"""PhoenixA HTTP client — wraps all kg domain API calls."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from atlas.core.config import get_config

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _base_url() -> str:
    cfg = get_config()["dept_services"]["phoenixA"]
    return f"http://{cfg['host']}:{cfg['port']}"


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=_base_url(), timeout=30.0)
    return _client


async def close():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _unwrap(resp: httpx.Response) -> Any:
    """Extract data from the standard apiResponse wrapper."""
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


# ── Documents ──────────────────────────────────────────────────────────────

async def create_document(doc: dict) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/kg/documents", json=doc)
    return _unwrap(resp)


async def list_documents(
    doc_type: str = "",
    source_type: str = "",
    processed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    client = await get_client()
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if doc_type:
        params["doc_type"] = doc_type
    if source_type:
        params["source_type"] = source_type
    if processed is not None:
        params["processed"] = str(processed).lower()
    resp = await client.get("/api/v1/kg/documents", params=params)
    data = _unwrap(resp)
    return data if isinstance(data, list) else []


async def get_document(doc_id: str) -> dict | None:
    client = await get_client()
    resp = await client.get(f"/api/v1/kg/documents/{doc_id}")
    if resp.status_code == 404:
        return None
    return _unwrap(resp)


async def update_document(doc_id: str, updates: dict) -> None:
    client = await get_client()
    resp = await client.put(f"/api/v1/kg/documents/{doc_id}", json=updates)
    resp.raise_for_status()


# ── Extractions ────────────────────────────────────────────────────────────

async def create_extraction(ext: dict) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/kg/extractions", json=ext)
    return _unwrap(resp)


async def list_extractions(
    doc_id: str = "",
    prompt_version: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    client = await get_client()
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if doc_id:
        params["doc_id"] = doc_id
    if prompt_version:
        params["prompt_version"] = prompt_version
    if status:
        params["status"] = status
    resp = await client.get("/api/v1/kg/extractions", params=params)
    data = _unwrap(resp)
    return data if isinstance(data, list) else []


async def get_extraction(ext_id: int) -> dict | None:
    client = await get_client()
    resp = await client.get(f"/api/v1/kg/extractions/{ext_id}")
    if resp.status_code == 404:
        return None
    return _unwrap(resp)


# ── Events ─────────────────────────────────────────────────────────────────

async def create_event(event: dict) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/kg/events", json=event)
    return _unwrap(resp)


async def list_events(
    fingerprint: str = "",
    event_type: str = "",
    entity_name: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    client = await get_client()
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if fingerprint:
        params["fingerprint"] = fingerprint
    if event_type:
        params["event_type"] = event_type
    if entity_name:
        params["entity_name"] = entity_name
    resp = await client.get("/api/v1/kg/events", params=params)
    data = _unwrap(resp)
    return data if isinstance(data, list) else []


async def get_event(event_id: int) -> dict | None:
    client = await get_client()
    resp = await client.get(f"/api/v1/kg/events/{event_id}")
    if resp.status_code == 404:
        return None
    return _unwrap(resp)


async def update_event(event_id: int, updates: dict) -> None:
    client = await get_client()
    resp = await client.put(f"/api/v1/kg/events/{event_id}", json=updates)
    resp.raise_for_status()


async def list_recent_events(days: int = 7, limit: int = 50) -> list[dict]:
    client = await get_client()
    resp = await client.get("/api/v1/kg/events/recent", params={"days": days, "limit": limit})
    data = _unwrap(resp)
    return data if isinstance(data, list) else []


# ── Graph Ingestions ───────────────────────────────────────────────────────

async def create_graph_ingestion(gi: dict) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/kg/graph-ingestions", json=gi)
    return _unwrap(resp)


# ── Daily Runs ─────────────────────────────────────────────────────────────

async def create_daily_run(run: dict) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/kg/daily-runs", json=run)
    return _unwrap(resp)


async def list_daily_runs(limit: int = 30, offset: int = 0) -> list[dict]:
    client = await get_client()
    resp = await client.get("/api/v1/kg/daily-runs", params={"limit": limit, "offset": offset})
    data = _unwrap(resp)
    return data if isinstance(data, list) else []


# ── Impact Logs ────────────────────────────────────────────────────────────

async def create_impact_log(log: dict) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/kg/impact-logs", json=log)
    return _unwrap(resp)


async def list_impact_logs(
    event_id: int | None = None,
    event_name: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    client = await get_client()
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if event_id is not None:
        params["event_id"] = event_id
    if event_name:
        params["event_name"] = event_name
    resp = await client.get("/api/v1/kg/impact-logs", params=params)
    data = _unwrap(resp)
    return data if isinstance(data, list) else []


# ── Graph (Neo4j via PhoenixA) ─────────────────────────────────────────────

async def run_cypher(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a read-only Cypher query via PhoenixA."""
    client = await get_client()
    resp = await client.post("/api/v1/graph/cypher", json={"cypher": cypher, "params": params or {}})
    data = _unwrap(resp)
    return data if isinstance(data, list) else []


async def run_cypher_write(cypher: str, params: dict | None = None) -> dict:
    """Execute a write Cypher query via PhoenixA."""
    client = await get_client()
    resp = await client.post("/api/v1/graph/cypher/write", json={"cypher": cypher, "params": params or {}})
    return _unwrap(resp)


async def merge_node(label: str, merge_key: str, merge_value: str, props: dict | None = None) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/graph/nodes/merge", json={
        "label": label, "merge_key": merge_key, "merge_value": merge_value, "props": props or {},
    })
    return _unwrap(resp)


async def merge_nodes_batch(nodes: list[dict]) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/graph/nodes/merge-batch", json=nodes)
    return _unwrap(resp)


async def merge_edge(
    from_label: str, from_key: str, from_value: str,
    to_label: str, to_key: str, to_value: str,
    rel_type: str, attrs: dict | None = None,
) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/graph/edges/merge", json={
        "from_label": from_label, "from_key": from_key, "from_value": from_value,
        "to_label": to_label, "to_key": to_key, "to_value": to_value,
        "rel_type": rel_type, "attrs": attrs or {},
    })
    return _unwrap(resp)


async def merge_edges_batch(edges: list[dict]) -> dict:
    client = await get_client()
    resp = await client.post("/api/v1/graph/edges/merge-batch", json=edges)
    return _unwrap(resp)


async def graph_search_nodes(q: str, limit: int = 20) -> list[dict]:
    client = await get_client()
    resp = await client.get("/api/v1/graph/search", params={"q": q, "limit": limit})
    data = _unwrap(resp)
    return data.get("results", []) if isinstance(data, dict) else []


async def graph_get_company(name: str) -> dict:
    client = await get_client()
    resp = await client.get(f"/api/v1/graph/company/{name}")
    return _unwrap(resp)


async def graph_get_company_chain(name: str, max_hops: int = 3) -> dict:
    client = await get_client()
    resp = await client.get(f"/api/v1/graph/company/{name}/chain", params={"max_hops": max_hops})
    return _unwrap(resp)


async def graph_get_company_timeline(name: str) -> list[dict]:
    client = await get_client()
    resp = await client.get(f"/api/v1/graph/company/{name}/timeline")
    data = _unwrap(resp)
    return data.get("timeline", []) if isinstance(data, dict) else []


async def graph_get_competitors(name: str) -> list[dict]:
    client = await get_client()
    resp = await client.get(f"/api/v1/graph/company/{name}/competitors")
    data = _unwrap(resp)
    return data.get("competitors", []) if isinstance(data, dict) else []


async def graph_get_event_impacts(event_name: str) -> list[dict]:
    client = await get_client()
    resp = await client.get(f"/api/v1/graph/event/{event_name}/impacts")
    data = _unwrap(resp)
    return data.get("impacts", []) if isinstance(data, dict) else []


async def graph_get_stats() -> dict:
    client = await get_client()
    resp = await client.get("/api/v1/graph/stats")
    return _unwrap(resp)


async def graph_ensure_schema() -> None:
    client = await get_client()
    resp = await client.post("/api/v1/graph/schema/ensure")
    resp.raise_for_status()


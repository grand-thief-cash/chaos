"""Impact analysis engine — propagate events along the supply chain graph.

All Neo4j queries go through PhoenixA's /api/v1/graph/* endpoints.
"""
from __future__ import annotations

import logging
from typing import Any

from atlas.connectors.llm_client import call_summary
from atlas.connectors import phoenixa_client

logger = logging.getLogger(__name__)

# Relationship types that transmit impact along the supply chain
_TRANSMISSION_RELS = [
    "SUPPLIER_OF", "CUSTOMER_OF",
    "DEPENDS_ON_RESOURCE", "CONSUMES_RESOURCE",
    "SUBSIDIARY_OF",
]


async def analyze_event_impact(
    event_name: str,
    max_hops: int = 3,
) -> dict[str, Any]:
    """Analyze the impact of an event on companies via graph traversal + LLM reasoning.

    1. Find the event and its direct IMPACT_ON edges.
    2. BFS along supply-chain relationships to find indirectly affected companies.
    3. Call LLM to generate impact reasoning for key companies.
    """
    direct = await _get_direct_impacts(event_name)
    indirect = await _get_indirect_impacts(event_name, max_hops)

    # Merge and deduplicate
    all_companies = {}
    for item in direct:
        all_companies[item["company"]] = {**item, "hop": 0, "type": "direct"}
    for item in indirect:
        name = item["company"]
        if name not in all_companies:
            all_companies[name] = {**item, "type": "indirect"}

    # For top affected companies, use LLM to generate detailed reasoning
    top_companies = sorted(
        all_companies.values(),
        key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.get("strength", "low"), 0),
        reverse=True,
    )[:10]

    analysis_text = ""
    if top_companies:
        graph_context = _format_graph_context(event_name, top_companies)
        llm_result = await call_summary(context=graph_context, prompt=_IMPACT_ANALYSIS_PROMPT)
        analysis_text = llm_result.get("content", "")

    result = {
        "event": event_name,
        "direct_impacts": direct,
        "indirect_impacts": indirect,
        "total_affected": len(all_companies),
        "llm_analysis": analysis_text,
    }

    # Persist impact log via phoenixA
    try:
        await phoenixa_client.create_impact_log({
            "event_name": event_name,
            "impact_json": result,
        })
    except Exception as e:
        logger.warning("Failed to persist impact log: %s", e)

    return result


async def _get_direct_impacts(event_name: str) -> list[dict]:
    """Get directly impacted companies via PhoenixA graph API."""
    return await phoenixa_client.graph_get_event_impacts(event_name)


async def _get_indirect_impacts(event_name: str, max_hops: int) -> list[dict]:
    """BFS from directly impacted companies along supply chain rels via PhoenixA."""
    rel_filter = "|".join(_TRANSMISSION_RELS)
    cypher = f"""
    MATCH (e:Event {{name: $name}})-[:IMPACT_ON]->(direct:Company)
    MATCH path = (direct)-[:{rel_filter}*1..{max_hops}]-(indirect:Company)
    WHERE indirect <> direct
    WITH indirect, min(length(path)) AS hop,
         [r IN relationships(path) | type(r)] AS rel_chain
    RETURN DISTINCT indirect.normalized_name AS company,
           indirect.ticker AS ticker, hop,
           rel_chain[0] AS via_relation
    ORDER BY hop
    LIMIT 50
    """
    return await phoenixa_client.run_cypher(cypher, {"name": event_name})


def _format_graph_context(event_name: str, companies: list[dict]) -> str:
    lines = [f"事件: {event_name}", "", "受影响公司:"]
    for c in companies:
        lines.append(
            f"- {c.get('company', '?')} (类型:{c.get('type','?')}, "
            f"方向:{c.get('direction','?')}, 影响:{c.get('strength','?')}, "
            f"路径:{c.get('path','')})"
        )
    return "\n".join(lines)


_IMPACT_ANALYSIS_PROMPT = """你是一个专业的金融产业链分析师。
根据以下事件及受影响公司的图谱数据，为投资者生成影响分析报告。

要求：
1. 按影响程度从高到低排列
2. 说明影响传导路径
3. 区分短期/长期影响
4. 给出投资建议方向（利好/利空/中性）
5. 用简洁专业的语言
6. 不要编造信息，只基于提供的数据分析

输出格式：Markdown
"""


async def analyze_company_exposure(company_name: str) -> dict[str, Any]:
    """Analyze a company's risk exposure via PhoenixA graph API."""
    cypher = """
    MATCH (c:Company {normalized_name: $name})
    OPTIONAL MATCH (e:Event)-[r1:IMPACT_ON]->(c)
    OPTIONAL MATCH (c)-[r2:DEPENDS_ON_RESOURCE|CONSUMES_RESOURCE]->(res:Resource)
    OPTIONAL MATCH (p:Policy)-[r3:IMPACTED_BY_POLICY]-(c)
    RETURN collect(DISTINCT {event: e.name, direction: r1.impact_direction,
                             type: r1.impact_type, strength: r1.impact_strength}) AS events,
           collect(DISTINCT {resource: res.name, category: res.category,
                             price_trend: res.price_trend,
                             supply_status: res.supply_status}) AS resources,
           collect(DISTINCT {policy: p.name, scope: p.impact_scope}) AS policies
    """
    rows = await phoenixa_client.run_cypher(cypher, {"name": company_name})

    if not rows:
        return {"company": company_name, "events": [], "resources": [], "policies": []}

    result = rows[0]
    return {
        "company": company_name,
        "events": [e for e in (result.get("events") or []) if e.get("event")],
        "resources": [r for r in (result.get("resources") or []) if r.get("resource")],
        "policies": [p for p in (result.get("policies") or []) if p.get("policy")],
    }

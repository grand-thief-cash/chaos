"""Impact analysis engine — propagate events along the supply chain graph."""
from __future__ import annotations

import logging
from typing import Any

from atlas.connectors.neo4j_client import get_session
from atlas.connectors.llm_client import call_summary

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
    direct = _get_direct_impacts(event_name)
    indirect = _get_indirect_impacts(event_name, max_hops)

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

    if top_companies:
        graph_context = _format_graph_context(event_name, top_companies)
        llm_result = await call_summary(
            context=graph_context,
            prompt=_IMPACT_ANALYSIS_PROMPT,
        )
        analysis_text = llm_result.get("content", "")
    else:
        analysis_text = ""

    return {
        "event": event_name,
        "direct_impacts": direct,
        "indirect_impacts": indirect,
        "total_affected": len(all_companies),
        "llm_analysis": analysis_text,
    }


def _get_direct_impacts(event_name: str) -> list[dict]:
    cypher = """
    MATCH (e:Event {name: $name})-[r:IMPACT_ON]->(c:Company)
    RETURN c.normalized_name AS company, c.ticker AS ticker,
           r.impact_direction AS direction, r.impact_type AS type,
           r.impact_strength AS strength, r.transmission_path AS path
    """
    with get_session() as session:
        return session.run(cypher, name=event_name).data()


def _get_indirect_impacts(event_name: str, max_hops: int) -> list[dict]:
    """BFS from directly impacted companies along supply chain rels."""
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
    with get_session() as session:
        return session.run(cypher, name=event_name).data()


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
    """Analyze a company's risk exposure — what events/resources/policies affect it."""
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
    with get_session() as session:
        result = session.run(cypher, name=company_name).single()

    if result is None:
        return {"company": company_name, "events": [], "resources": [], "policies": []}

    return {
        "company": company_name,
        "events": [e for e in result["events"] if e.get("event")],
        "resources": [r for r in result["resources"] if r.get("resource")],
        "policies": [p for p in result["policies"] if p.get("policy")],
    }


async def generate_company_review(company_name: str) -> dict[str, Any]:
    """Generate an investment-oriented company development review using graph data + LLM."""
    from atlas.services.graph_service import (
        get_company_full, get_company_timeline, get_competitors,
    )

    company_data = get_company_full(company_name)
    if not company_data:
        return {"company": company_name, "review": "未找到该公司信息"}

    timeline = get_company_timeline(company_name)
    competitors = get_competitors(company_name)
    exposure = await analyze_company_exposure(company_name)

    context = _format_review_context(company_name, company_data, timeline, competitors, exposure)

    llm_result = await call_summary(context=context, prompt=_COMPANY_REVIEW_PROMPT)

    return {
        "company": company_name,
        "review": llm_result.get("content", ""),
        "graph_data": {
            "relationships_count": len(company_data.get("relationships", [])),
            "events_count": len(timeline),
            "competitors_count": len(competitors),
            "risk_exposure": exposure,
        },
    }


def _format_review_context(
    name: str,
    company_data: dict,
    timeline: list[dict],
    competitors: list[dict],
    exposure: dict,
) -> str:
    lines = [f"公司: {name}", ""]

    # Company info
    info = company_data.get("company", {})
    if info:
        lines.append(f"基本信息: ticker={info.get('ticker','')}, country={info.get('country','')}")

    # Relationships summary
    rels = company_data.get("relationships", [])
    if rels:
        lines.append(f"\n关系总数: {len(rels)}")
        for r in rels[:30]:
            lines.append(
                f"  - [{r.get('rel_type','')}] → {r.get('neighbor',{}).get('name','')} "
                f"({r.get('neighbor_label','')})"
            )

    # Timeline
    if timeline:
        lines.append(f"\n时间线事件 ({len(timeline)}):")
        for t in timeline[:20]:
            lines.append(f"  - [{t.get('time','')}] {t.get('rel_type','')} → {t.get('neighbor_name','')}")

    # Competitors
    if competitors:
        lines.append(f"\n竞品 ({len(competitors)}):")
        for c in competitors:
            lines.append(f"  - {c.get('competitor','')} (产品:{c.get('product','')}, 类型:{c.get('competition_type','')})")

    # Risk exposure
    if exposure.get("resources"):
        lines.append("\n资源依赖:")
        for r in exposure["resources"]:
            lines.append(f"  - {r.get('resource','')} (价格趋势:{r.get('price_trend','')}, 供给:{r.get('supply_status','')})")

    return "\n".join(lines)


_COMPANY_REVIEW_PROMPT = """你是一个专业的金融分析师。
根据以下知识图谱数据，为投资者生成该公司的发展综述。

重点关注：
1. 产业链位置与核心竞争力
2. 主要产品与市场
3. 上下游关系及议价能力
4. 竞品格局
5. 主要风险敞口（资源依赖/政策风险/竞争压力）
6. 近期重要事件及其影响
7. 投资关注要点与建议

要求：
- 客观、专业、简洁
- 不编造信息，只基于提供的数据
- 用 Markdown 格式输出
"""


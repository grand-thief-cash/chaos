"""Company review service — aggregates graph data + LLM to generate investment review."""
from __future__ import annotations

import logging

from atlas.connectors.llm_client import call_summary
from atlas.services.graph_query import (
    get_company_full, get_company_timeline, get_competitors,
)
from atlas.services.impact import analyze_company_exposure
from atlas.models.impact import CompanyReview, CompanyReviewData

logger = logging.getLogger(__name__)

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


async def generate_company_review(company_name: str) -> CompanyReview:
    """Generate an investment-oriented company development review."""
    company_data = await get_company_full(company_name)
    if not company_data:
        return CompanyReview(company=company_name, review_text="未找到该公司信息")

    timeline = await get_company_timeline(company_name)
    competitors = await get_competitors(company_name)
    exposure = await analyze_company_exposure(company_name)

    # Build structured data
    review_data = _build_review_data(company_name, company_data, competitors, exposure)

    # Format context for LLM
    context = _format_review_context(company_name, company_data, timeline, competitors, exposure)

    # Generate review via LLM
    llm_result = await call_summary(context=context, prompt=_COMPANY_REVIEW_PROMPT)

    return CompanyReview(
        company=company_name,
        review_text=llm_result.get("content", ""),
        graph_data=review_data,
    )


def _build_review_data(
    name: str,
    company_data: dict,
    competitors: list[dict],
    exposure: dict,
) -> CompanyReviewData:
    info = company_data.get("company", {})
    rels = company_data.get("relationships", [])

    industries = []
    products = []
    suppliers = []
    customers = []
    comp_names = []

    for r in rels:
        rel_type = r.get("rel_type", "")
        neighbor_name = r.get("neighbor", {}).get("name", "")
        if rel_type == "BELONGS_TO_INDUSTRY":
            industries.append(neighbor_name)
        elif rel_type == "PRODUCES":
            products.append(neighbor_name)
        elif rel_type == "SUPPLIER_OF":
            customers.append(neighbor_name)
        elif rel_type == "CUSTOMER_OF":
            suppliers.append(neighbor_name)

    for c in competitors:
        comp_names.append(c.get("competitor", ""))

    return CompanyReviewData(
        company_name=name,
        ticker=info.get("ticker", ""),
        value_chain_position=info.get("value_chain_position", ""),
        industries=industries,
        products=products,
        suppliers=suppliers,
        customers=customers,
        competitors=comp_names,
        resources=exposure.get("resources", []),
        recent_events=exposure.get("events", []),
        risk_exposure=exposure,
        relationships_count=len(rels),
    )


def _format_review_context(
    name: str,
    company_data: dict,
    timeline: list[dict],
    competitors: list[dict],
    exposure: dict,
) -> str:
    lines = [f"公司: {name}", ""]

    info = company_data.get("company", {})
    if info:
        lines.append(f"基本信息: ticker={info.get('ticker', '')}, country={info.get('country', '')}")

    rels = company_data.get("relationships", [])
    if rels:
        lines.append(f"\n关系总数: {len(rels)}")
        for r in rels[:30]:
            lines.append(
                f"  - [{r.get('rel_type', '')}] → {r.get('neighbor', {}).get('name', '')} "
                f"({r.get('neighbor_label', '')})"
            )

    if timeline:
        lines.append(f"\n时间线事件 ({len(timeline)}):")
        for t in timeline[:20]:
            lines.append(f"  - [{t.get('time', '')}] {t.get('rel_type', '')} → {t.get('neighbor_name', '')}")

    if competitors:
        lines.append(f"\n竞品 ({len(competitors)}):")
        for c in competitors:
            lines.append(f"  - {c.get('competitor', '')} (产品:{c.get('product', '')}, 类型:{c.get('competition_type', '')})")

    if exposure.get("resources"):
        lines.append("\n资源依赖:")
        for r in exposure["resources"]:
            lines.append(f"  - {r.get('resource', '')} (价格趋势:{r.get('price_trend', '')}, 供给:{r.get('supply_status', '')})")

    return "\n".join(lines)




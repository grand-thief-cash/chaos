"""Daily pipeline — orchestrates news fetch → filter → extract → graph update → event dedup → impact analysis."""
from __future__ import annotations

import logging
from datetime import datetime, date

from atlas.connectors.llm_client import call_filter
from atlas.connectors import phoenixa_client
from atlas.connectors.news_fetcher import fetch_news_from_rss
from atlas.models.document import DailyRunRecord, DocStatus
from atlas.services.ingestion import split_into_chunks
from atlas.services.llm_extractor import extract_from_chunk
from atlas.services.graph_builder import build_graph_from_extraction
from atlas.services.event_dedup import dedup_event
from atlas.core.config import get_config

logger = logging.getLogger(__name__)


# ── News relevance filter prompt ───────────────────────────────────────────

_FILTER_PROMPT = """你是一个金融新闻过滤器。判断以下新闻是否与产业链/上市公司/宏观政策/行业事件相关。

回复格式（仅 JSON）：
{"relevant": true/false, "reason": "一句话理由"}

过滤标准 — 保留以下类型：
- 上市公司公告/财报/业绩
- 行业政策/监管变化
- 原材料/资源价格变动
- 产业链上下游动态
- 重大并购/投资/合作
- 宏观经济政策

过滤掉：
- 娱乐/体育/社会新闻
- 无实质内容的评论/鸡汤
- 广告/软文
"""

_CLASSIFY_PROMPT = """判断以下文本属于哪种类型，回复仅 JSON：
{"source_type": "graph_building" 或 "event_triggering", "doc_type": "...", "reason": "..."}

graph_building: 研报、财报、行业分析、产品/供应链/竞争格局等结构性内容
event_triggering: 新闻、政策发布、价格变动、突发事件等时效性内容

doc_type 可选: earnings|research|industry|news|policy|announcement
"""


async def filter_news(news_text: str) -> bool:
    """Return True if the news is relevant to industry chain analysis."""
    result = await call_filter(news_text[:500], _FILTER_PROMPT)
    parsed = result.get("parsed")
    if parsed and isinstance(parsed, dict):
        return parsed.get("relevant", False)
    return False


async def classify_document(text: str) -> dict:
    """Classify a document as graph_building or event_triggering."""
    result = await call_filter(text[:500], _CLASSIFY_PROMPT)
    parsed = result.get("parsed")
    if parsed and isinstance(parsed, dict):
        return {
            "source_type": parsed.get("source_type", "event_triggering"),
            "doc_type": parsed.get("doc_type", "news"),
        }
    return {"source_type": "event_triggering", "doc_type": "news"}


# ── Pipeline orchestration ─────────────────────────────────────────────────

async def run_daily_pipeline(
    news_items: list[dict[str, str]] | None = None,
) -> DailyRunRecord:
    """Run the full daily pipeline with event dedup integration."""
    cfg = get_config()
    today = date.today().isoformat()
    run = DailyRunRecord(run_date=today, status=DocStatus.PROCESSING, started_at=datetime.now())

    if news_items is None:
        news_items = await fetch_news_from_rss()

    run.news_fetched = len(news_items)
    logger.info("Daily pipeline started: %d news items fetched", run.news_fetched)

    # Step 1: Filter
    relevant_items = []
    for item in news_items:
        text = f"{item.get('title', '')}\n{item.get('content', '')}"
        if await filter_news(text):
            relevant_items.append(item)

    run.news_relevant = len(relevant_items)
    logger.info("After filtering: %d/%d relevant", run.news_relevant, run.news_fetched)

    # Step 2: Extract, build graph, dedup events
    max_extraction = cfg.get("pipeline", {}).get("daily_max_extraction", 50)
    total_nodes = 0
    total_edges = 0
    total_cost = 0.0
    events_new = 0
    events_deduped = 0

    for idx, item in enumerate(relevant_items[:max_extraction]):
        text = f"{item.get('title', '')}\n{item.get('content', '')}"
        chunks = split_into_chunks(text)

        for i, chunk in enumerate(chunks):
            result, raw = await extract_from_chunk(
                chunk, doc_id=f"news_{today}_{idx}_{i}", chunk_index=i
            )
            total_cost += raw.get("cost", 0.0)

            if result is not None:
                # Build graph
                counts = await build_graph_from_extraction(result)
                total_nodes += counts["nodes_created"]
                total_edges += counts["edges_created"]

                # Process events from extraction
                for event_node in result.nodes.events:
                    dedup_result = await dedup_event(
                        entity_name=event_node.name,
                        event_type=event_node.type.value if hasattr(event_node.type, 'value') else str(event_node.type),
                        direction="neutral",
                        description=f"{event_node.name} ({event_node.impact_scope.value if hasattr(event_node.impact_scope, 'value') else ''})",
                        source_doc_id=f"news_{today}_{idx}_{i}",
                    )
                    if dedup_result.is_new:
                        events_new += 1
                    else:
                        events_deduped += 1

    run.entities_created = total_nodes
    run.edges_created = total_edges
    run.total_cost_usd = total_cost
    run.impacts_generated = events_new
    run.status = DocStatus.COMPLETED
    run.completed_at = datetime.now()

    # Record daily run in phoenixA
    try:
        await phoenixa_client.create_daily_run({
            "run_date": today,
            "docs_fetched": run.news_fetched,
            "docs_event": run.news_relevant,
            "events_new": events_new,
            "events_deduped": events_deduped,
            "extractions_ok": total_nodes,
            "impacts_generated": events_new,
            "total_cost_usd": total_cost,
            "status": "completed",
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        })
    except Exception as e:
        logger.warning("Failed to record daily run: %s", e)

    logger.info(
        "Daily pipeline completed: nodes=%d, edges=%d, events_new=%d, deduped=%d, cost=$%.4f",
        total_nodes, total_edges, events_new, events_deduped, total_cost,
    )
    return run


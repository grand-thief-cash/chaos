"""Daily pipeline — orchestrates news fetch → filter → extract → graph update → impact analysis."""
from __future__ import annotations

import logging
from datetime import datetime, date

from atlas.connectors.llm_client import call_filter
from atlas.models.document import DailyRunRecord, DocStatus
from atlas.services.ingestion import split_into_chunks
from atlas.services.llm_extractor import extract_from_chunk
from atlas.services.graph_service import ingest_extraction_result
from atlas.core.config import get_config

logger = logging.getLogger(__name__)


# ── News relevance filter prompt ───────────────────────────────────────────────

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


async def filter_news(news_text: str) -> bool:
    """Return True if the news is relevant to industry chain analysis."""
    result = await call_filter(news_text[:500], _FILTER_PROMPT)
    parsed = result.get("parsed")
    if parsed and isinstance(parsed, dict):
        return parsed.get("relevant", False)
    return False


# ── Pipeline orchestration ─────────────────────────────────────────────────────

async def run_daily_pipeline(
    news_items: list[dict[str, str]] | None = None,
) -> DailyRunRecord:
    """Run the full daily pipeline.

    Args:
        news_items: List of {"title": ..., "content": ..., "url": ...}.
                    If None, will attempt to fetch from configured sources.

    Returns:
        DailyRunRecord with statistics.
    """
    cfg = get_config()
    today = date.today().isoformat()
    run = DailyRunRecord(run_date=today, status=DocStatus.PROCESSING, started_at=datetime.now())

    if news_items is None:
        news_items = await _fetch_news()

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

    # Step 2: Extract & ingest
    max_extraction = cfg.get("pipeline", {}).get("daily_max_extraction", 50)
    total_nodes = 0
    total_edges = 0
    total_cost = 0.0

    for item in relevant_items[:max_extraction]:
        text = f"{item.get('title', '')}\n{item.get('content', '')}"
        chunks = split_into_chunks(text)

        for i, chunk in enumerate(chunks):
            result, raw = await extract_from_chunk(
                chunk, doc_id=f"news_{today}_{i}", chunk_index=i
            )
            total_cost += raw.get("cost", 0.0)

            if result is not None:
                counts = ingest_extraction_result(result)
                total_nodes += counts["nodes"]
                total_edges += counts["edges"]

    run.entities_created = total_nodes
    run.edges_created = total_edges
    run.total_cost_usd = total_cost
    run.status = DocStatus.COMPLETED
    run.completed_at = datetime.now()

    logger.info(
        "Daily pipeline completed: nodes=%d, edges=%d, cost=$%.4f",
        total_nodes, total_edges, total_cost,
    )
    return run


async def _fetch_news() -> list[dict[str, str]]:
    """Fetch news from configured sources.

    TODO: Implement actual news fetching from RSS/API sources.
    This is a placeholder — integrate with tools/py/crawler or external APIs.
    """
    logger.warning("News fetching not yet implemented — returning empty list")
    return []


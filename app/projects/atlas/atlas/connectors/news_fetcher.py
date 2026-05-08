"""News fetcher — pulls news from RSS sources for the daily pipeline."""
from __future__ import annotations

import logging
from typing import Any

from atlas.core.config import get_config

logger = logging.getLogger(__name__)


async def fetch_news_from_rss() -> list[dict[str, str]]:
    """Fetch news items from configured RSS sources.

    Returns list of {"title": ..., "content": ..., "url": ..., "source": ...}
    """
    cfg = get_config()
    sources = cfg.get("pipeline", {}).get("news_sources", [])
    max_items = cfg.get("pipeline", {}).get("daily_max_news", 200)

    all_items: list[dict[str, str]] = []

    for source in sources:
        if source.get("type") != "rss":
            continue
        url = source.get("url", "")
        name = source.get("name", "unknown")
        if not url:
            logger.debug("Skipping RSS source %s — no URL configured", name)
            continue

        items = await _parse_rss_feed(url, name)
        all_items.extend(items)

        if len(all_items) >= max_items:
            all_items = all_items[:max_items]
            break

    logger.info("Fetched %d news items from %d RSS sources", len(all_items), len(sources))
    return all_items


async def _parse_rss_feed(url: str, source_name: str) -> list[dict[str, str]]:
    """Parse a single RSS feed URL."""
    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser not installed — RSS fetching disabled")
        return []

    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries:
            # Extract content: try content field, then summary, then description
            content = ""
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "description"):
                content = entry.description

            # Clean HTML tags from content
            content = _strip_html(content)

            items.append({
                "title": getattr(entry, "title", ""),
                "content": content[:10000],  # Limit content length
                "url": getattr(entry, "link", ""),
                "source": source_name,
                "published": getattr(entry, "published", ""),
            })
        logger.info("Parsed %d entries from RSS source %s", len(items), source_name)
        return items
    except Exception as e:
        logger.error("Failed to parse RSS feed %s: %s", url, e)
        return []


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(text, "html.parser").get_text(separator="\n", strip=True)
    except ImportError:
        import re
        return re.sub(r"<[^>]+>", "", text)


"""Pipeline trigger endpoints — called by cronjob or manually."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from atlas.services.daily_pipeline import run_daily_pipeline

router = APIRouter()


class NewsItem(BaseModel):
    title: str = ""
    content: str = ""
    url: str = ""


class DailyTriggerRequest(BaseModel):
    news_items: list[NewsItem] | None = None


@router.post("/daily")
async def trigger_daily(req: DailyTriggerRequest | None = None):
    """Trigger the daily news → extraction → graph update → impact pipeline.

    Can be called by cronjob with no body (auto-fetch news),
    or with explicit news_items for testing.
    """
    items = None
    if req and req.news_items:
        items = [item.model_dump() for item in req.news_items]

    run = await run_daily_pipeline(news_items=items)
    return run.model_dump()


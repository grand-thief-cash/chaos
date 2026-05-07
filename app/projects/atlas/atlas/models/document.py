"""Document metadata & task tracking models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentMeta(BaseModel):
    doc_id: str
    title: str = ""
    source_type: str = "unknown"  # earnings | research | news | announcement | policy
    source_url: str = ""
    company_name: str = ""
    content_hash: str = ""
    status: DocStatus = DocStatus.PENDING
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None


class ExtractionTask(BaseModel):
    id: int = 0
    doc_id: str
    chunk_index: int
    llm_model: str = ""
    prompt_version: str = "v5"
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    status: DocStatus = DocStatus.PENDING
    error_message: str = ""
    raw_response: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class DailyRunRecord(BaseModel):
    id: int = 0
    run_date: str  # YYYY-MM-DD
    news_fetched: int = 0
    news_relevant: int = 0
    entities_created: int = 0
    edges_created: int = 0
    impacts_generated: int = 0
    total_cost_usd: float = 0.0
    status: DocStatus = DocStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


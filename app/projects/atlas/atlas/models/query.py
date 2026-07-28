from __future__ import annotations

from typing import Any

from pydantic import Field

from atlas.models.extraction import StrictModel


class QueryToolCall(StrictModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class QueryPlan(StrictModel):
    question: str
    calls: list[QueryToolCall]
    answer_instruction: str


class QueryAnswer(StrictModel):
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)

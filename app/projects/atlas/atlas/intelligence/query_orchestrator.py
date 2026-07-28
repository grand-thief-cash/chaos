from __future__ import annotations

from typing import Any, Protocol

from atlas.models import QueryAnswer, QueryPlan


class QueryPlanningModel(Protocol):
    async def plan(self, question: str, allowed_tools: list[str]) -> QueryPlan: ...
    async def answer(self, question: str, observations: list[dict[str, Any]]) -> QueryAnswer: ...


class QueryToolbox(Protocol):
    async def execute(self, tool: str, arguments: dict[str, Any]) -> Any: ...


class QueryOrchestrator:
    ALLOWED_TOOLS = (
        "search_entities",
        "get_entity_neighborhood",
        "get_claims",
        "get_security_profile",
        "get_financial_metrics",
    )

    def __init__(self, model: QueryPlanningModel, toolbox: QueryToolbox, *, maximum_tool_calls: int = 8):
        self.model = model
        self.toolbox = toolbox
        self.maximum_tool_calls = maximum_tool_calls

    async def run(self, question: str) -> QueryAnswer:
        plan = await self.model.plan(question, list(self.ALLOWED_TOOLS))
        if len(plan.calls) > self.maximum_tool_calls:
            raise ValueError("query plan exceeds tool-call limit")
        observations: list[dict[str, Any]] = []
        for call in plan.calls:
            if call.tool not in self.ALLOWED_TOOLS:
                raise ValueError(f"query plan requested forbidden tool: {call.tool}")
            result = await self.toolbox.execute(call.tool, call.arguments)
            observations.append({"tool": call.tool, "arguments": call.arguments, "result": result})
        answer = await self.model.answer(question, observations)
        unsupported = [
            citation
            for citation in answer.citations
            if not _citation_is_grounded(citation, observations)
        ]
        if unsupported:
            raise ValueError("query answer contains unsupported citations")
        answer.tool_trace = observations
        return answer


def _citation_is_grounded(
    citation: dict[str, Any],
    observations: list[dict[str, Any]],
) -> bool:
    if not citation:
        return False
    return any(
        all(candidate.get(key) == value for key, value in citation.items())
        for candidate in _walk_dicts(observations)
    )


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_dicts(nested)

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from atlas.core.clients import PhoenixAClient


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(ToolArgs):
    query: str = Field(min_length=1, max_length=256)
    limit: int = Field(default=20, ge=1, le=100)


class EntityArgs(ToolArgs):
    entity_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    limit: int = Field(default=100, ge=1, le=500)


class ClaimArgs(EntityArgs):
    predicate: str = Field(default="", pattern=r"^[A-Z0-9_]*$")


class FinancialArgs(ToolArgs):
    source: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    statement_type: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    security_id: int = Field(gt=0)
    start_date: str = Field(default="", pattern=r"^$|^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(default="", pattern=r"^$|^\d{4}-\d{2}-\d{2}$")


class PhoenixAQueryToolbox:
    def __init__(self, client: PhoenixAClient) -> None:
        self.client = client

    async def execute(self, tool: str, arguments: dict[str, Any]) -> Any:
        if tool == "search_entities":
            args = SearchArgs.model_validate(arguments)
            return await self.client.search_knowledge_entities(
                args.query, limit=args.limit, exact=False
            )
        if tool == "get_entity_neighborhood":
            args = EntityArgs.model_validate(arguments)
            return await self.client.get_graph_neighborhood(args.entity_id, args.limit)
        if tool == "get_claims":
            args = ClaimArgs.model_validate(arguments)
            return await self.client.list_claims(args.entity_id, args.predicate, args.limit)
        if tool == "get_security_profile":
            args = SearchArgs.model_validate(arguments)
            return await self.client.search_securities(args.query, args.limit)
        if tool == "get_financial_metrics":
            args = FinancialArgs.model_validate(arguments)
            return await self.client.query_financial_metrics(**args.model_dump())
        raise ValueError(f"unsupported tool: {tool}")

from __future__ import annotations

import json
from typing import Any

from atlas.core.clients import StructuredChatClient
from atlas.models import QueryAnswer, QueryPlan


class StructuredQueryModelAdapter:
    """Query planner/answer adapter shared by Ollama and paid providers."""

    def __init__(self, client: StructuredChatClient) -> None:
        self.client = client

    async def plan(self, question: str, allowed_tools: list[str]) -> QueryPlan:
        return await self.client.complete_model(
            QueryPlan,
            system_prompt=(
                "你是 Atlas 只读查询规划器。只能选择明确提供的工具；"
                "禁止请求 Cypher、SQL、写库、网络搜索或未列出的工具。"
            ),
            user_prompt=json.dumps(
                {"question": question, "allowed_tools": allowed_tools},
                ensure_ascii=False,
            ),
        )

    async def answer(
        self,
        question: str,
        observations: list[dict[str, Any]],
    ) -> QueryAnswer:
        return await self.client.complete_model(
            QueryAnswer,
            system_prompt=(
                "你是 Atlas 研究助手。答案只能由工具 observation 支持；"
                "找不到证据时明确说不知道，不得补充常识或伪造引用。"
            ),
            user_prompt=json.dumps(
                {"question": question, "observations": observations},
                ensure_ascii=False,
                default=str,
            ),
        )

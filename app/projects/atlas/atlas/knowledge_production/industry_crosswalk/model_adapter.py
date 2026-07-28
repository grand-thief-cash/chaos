from __future__ import annotations

import json

from pydantic import Field

from atlas.core.clients import StructuredChatClient
from atlas.models import CrosswalkMapping, TaxonomyNode
from atlas.models.extraction import StrictModel


class CrosswalkModelOutput(StrictModel):
    mappings: list[CrosswalkMapping] = Field(default_factory=list)


class StructuredCrosswalkModelAdapter:
    def __init__(self, client: StructuredChatClient) -> None:
        self.client = client

    async def map_taxonomies(
        self,
        source_nodes: list[TaxonomyNode],
        target_nodes: list[TaxonomyNode],
        validation_errors: list[str] | None = None,
    ) -> list[CrosswalkMapping]:
        output = await self.client.complete_model(
            CrosswalkModelOutput,
            system_prompt=(
                "你是产业分类 Crosswalk 映射器。每个 source_code 必须且只能输出一次。"
                "只能引用输入中的 target_code；没有合理目标时使用 "
                "NO_CANONICAL_MAPPING、target_code=null，"
                "并给出 exception_reason。不要为了覆盖率强行匹配。"
            ),
            user_prompt=json.dumps(
                {
                    "source_nodes": [item.model_dump(mode="json") for item in source_nodes],
                    "target_nodes": [item.model_dump(mode="json") for item in target_nodes],
                    "previous_validation_errors": validation_errors or [],
                },
                ensure_ascii=False,
            ),
        )
        return output.mappings

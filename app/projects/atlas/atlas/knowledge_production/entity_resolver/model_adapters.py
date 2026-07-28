from __future__ import annotations

import json
from typing import Protocol

from pydantic import Field

from atlas.core.clients import StructuredChatClient
from atlas.models import EntityCandidate, EntityMention
from atlas.models.extraction import StrictModel


class EntityCluster(StrictModel):
    cluster_id: str
    mention_ids: list[str] = Field(min_length=1)
    canonical_mention_id: str


class EntityClusterOutput(StrictModel):
    clusters: list[EntityCluster]


class EntityClusterer(Protocol):
    async def cluster(
        self, mentions: list[EntityMention]
    ) -> list[EntityCluster]: ...


class StructuredEntityClusterer:
    def __init__(self, client: StructuredChatClient) -> None:
        self.client = client

    async def cluster(
        self, mentions: list[EntityMention]
    ) -> list[EntityCluster]:
        if len(mentions) < 2:
            return [
                EntityCluster(
                    cluster_id=mention.mention_id,
                    mention_ids=[mention.mention_id],
                    canonical_mention_id=mention.mention_id,
                )
                for mention in mentions
            ]
        output = await self.client.complete_model(
            EntityClusterOutput,
            system_prompt=(
                "你是单份研报内的实体共指聚类器。只有当文中证据明确表明称呼指向"
                "同一现实实体时才能合并，例如全称/简称、中文名/英文名、股票代码或"
                "括号别名一致。错误合并比不合并更严重；不确定时保持独立。"
                "每个 mention_id 必须且只能出现一次，禁止创造 mention_id，"
                "不同 entity_type 禁止合并。"
            ),
            user_prompt=json.dumps(
                {
                    "mentions": [
                        mention.model_dump(mode="json")
                        for mention in mentions
                    ]
                },
                ensure_ascii=False,
            ),
        )
        self._validate(mentions, output.clusters)
        return output.clusters

    @staticmethod
    def _validate(
        mentions: list[EntityMention],
        clusters: list[EntityCluster],
    ) -> None:
        by_id = {mention.mention_id: mention for mention in mentions}
        clustered = [
            mention_id
            for cluster in clusters
            for mention_id in cluster.mention_ids
        ]
        if len(clustered) != len(set(clustered)):
            raise ValueError("entity clustering duplicated a mention")
        if set(clustered) != set(by_id):
            raise ValueError("entity clustering must cover every mention exactly once")
        for cluster in clusters:
            if cluster.canonical_mention_id not in cluster.mention_ids:
                raise ValueError("canonical mention must belong to its cluster")
            types = {
                by_id[mention_id].suggested_entity_type
                for mention_id in cluster.mention_ids
            }
            if len(types) != 1:
                raise ValueError("entity clustering cannot merge different entity types")


class CandidateRanking(StrictModel):
    candidate_id: str
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class CandidateRankingOutput(StrictModel):
    rankings: list[CandidateRanking]


class StructuredEntityCandidateReranker:
    def __init__(self, client: StructuredChatClient) -> None:
        self.client = client

    async def rerank(
        self,
        mention: EntityMention,
        candidates: list[EntityCandidate],
    ) -> list[EntityCandidate]:
        output = await self.client.complete_model(
            CandidateRankingOutput,
            system_prompt=(
                "你是实体候选重排器。只能对输入候选评分，不得创建新实体。"
                "优先使用明确的 ticker、国家、全称/简称和上下文证据；"
                "常识不足时降低分数，错误合并比 provisional entity 更严重。"
                "每个 candidate_id 必须且只能输出一次。"
            ),
            user_prompt=json.dumps(
                {
                    "mention": mention.model_dump(mode="json"),
                    "candidates": [
                        {
                            "candidate_id": str(candidate.entity.id),
                            "entity": candidate.entity.model_dump(mode="json"),
                            "security_id": candidate.security_id,
                            "retrieval_reasons": candidate.reasons,
                        }
                        for candidate in candidates
                    ],
                },
                ensure_ascii=False,
            ),
        )
        rankings = {item.candidate_id: item for item in output.rankings}
        expected = {str(item.entity.id) for item in candidates}
        if set(rankings) != expected:
            raise ValueError("entity reranker must score every candidate exactly once")
        return [
            candidate.model_copy(update={
                "score": rankings[str(candidate.entity.id)].score,
                "reasons": [
                    *candidate.reasons,
                    *rankings[str(candidate.entity.id)].reasons,
                ],
            })
            for candidate in candidates
        ]

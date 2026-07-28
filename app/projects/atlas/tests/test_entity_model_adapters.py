import pytest

from atlas.knowledge_production.entity_resolver import (
    StructuredEntityClusterer,
)
from atlas.knowledge_production.entity_resolver.model_adapters import (
    EntityCluster,
    EntityClusterOutput,
)
from atlas.models import EntityMention, EntityType


class Client:
    async def complete_model(self, model, **kwargs):
        return EntityClusterOutput(clusters=[
            EntityCluster(
                cluster_id="nvidia",
                mention_ids=["m1", "m2"],
                canonical_mention_id="m2",
            )
        ])


@pytest.mark.asyncio
async def test_document_clusterer_can_bind_cross_language_aliases():
    mentions = [
        EntityMention(
            mention_id="m1",
            mention="英伟达",
            suggested_entity_type=EntityType.COMPANY,
            context="英伟达（NVIDIA）发布产品。",
        ),
        EntityMention(
            mention_id="m2",
            mention="NVIDIA",
            suggested_entity_type=EntityType.COMPANY,
            context="英伟达（NVIDIA）发布产品。",
        ),
    ]
    clusters = await StructuredEntityClusterer(
        Client()  # type: ignore[arg-type]
    ).cluster(mentions)
    assert clusters[0].mention_ids == ["m1", "m2"]


@pytest.mark.asyncio
async def test_document_clusterer_rejects_missing_mentions():
    class InvalidClient:
        async def complete_model(self, model, **kwargs):
            return EntityClusterOutput(clusters=[
                EntityCluster(
                    cluster_id="only-one",
                    mention_ids=["m1"],
                    canonical_mention_id="m1",
                )
            ])

    mentions = [
        EntityMention(
            mention_id=mention_id,
            mention=mention_id,
            suggested_entity_type=EntityType.COMPANY,
            context="context",
        )
        for mention_id in ("m1", "m2")
    ]
    with pytest.raises(ValueError, match="cover every mention"):
        await StructuredEntityClusterer(
            InvalidClient()  # type: ignore[arg-type]
        ).cluster(mentions)

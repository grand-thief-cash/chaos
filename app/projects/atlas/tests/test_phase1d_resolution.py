import pytest

from atlas.knowledge_production.entity_resolver import EntityResolutionService, normalize_entity_name
from atlas.models import EntityCandidate, EntityMention, EntityType, KnowledgeEntity, ResolutionState


class Source:
    async def find_candidates(self, normalized_name, entity_type, ticker_hint):
        entity = KnowledgeEntity(
            canonical_name="NVIDIA Corporation",
            normalized_name="nvidiacorporation",
            entity_type="COMPANY",
            country_code="US",
            resolution_state=ResolutionState.RESOLVED_KNOWLEDGE_ENTITY,
        )
        return [EntityCandidate(entity=entity, score=0.98)]


@pytest.mark.asyncio
async def test_exact_alias_and_provisional_entity():
    assert normalize_entity_name("宁德时代股份有限公司") == "宁德时代"
    mention = EntityMention(
        mention_id="m1", mention="NVIDIA Corporation",
        suggested_entity_type=EntityType.COMPANY, context="NVIDIA 提供 GPU",
    )
    result = await EntityResolutionService(Source()).resolve(mention)
    assert result.method == "EXACT_ALIAS"
    assert result.entity.country_code == "US"

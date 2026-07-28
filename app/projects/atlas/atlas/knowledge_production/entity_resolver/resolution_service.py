from __future__ import annotations

from typing import Protocol

from atlas.knowledge_production.entity_resolver.name_normalizer import normalize_entity_name
from atlas.models import EntityCandidate, EntityMention, KnowledgeEntity, ResolutionState, ResolvedMention


class EntityCandidateSource(Protocol):
    async def find_candidates(
        self, normalized_name: str, entity_type: str, ticker_hint: str | None
    ) -> list[EntityCandidate]: ...


class CandidateReranker(Protocol):
    async def rerank(self, mention: EntityMention, candidates: list[EntityCandidate]) -> list[EntityCandidate]: ...


class EntityResolutionService:
    def __init__(
        self,
        source: EntityCandidateSource,
        reranker: CandidateReranker | None = None,
        *,
        auto_accept_threshold: float = 0.92,
        ambiguity_margin: float = 0.05,
    ) -> None:
        self.source = source
        self.reranker = reranker
        self.auto_accept_threshold = auto_accept_threshold
        self.ambiguity_margin = ambiguity_margin

    async def resolve(self, mention: EntityMention) -> ResolvedMention:
        normalized = normalize_entity_name(mention.mention)
        if not normalized:
            raise ValueError(
                f"entity mention normalizes to an empty name: {mention.mention_id}"
            )
        candidates = await self.source.find_candidates(
            normalized, mention.suggested_entity_type.value, mention.ticker_hint
        )
        exact = [
            item
            for item in candidates
            if item.entity.normalized_name == normalized
            or "EXACT_KNOWLEDGE_ALIAS" in item.reasons
            or "SECURITY_REGISTRY_EXACT" in item.reasons
        ]
        if len(exact) == 1:
            return self._resolved(mention, exact[0], "EXACT_ALIAS")
        ranked = await self.reranker.rerank(mention, candidates) if candidates and self.reranker else candidates
        ranked = sorted(ranked, key=lambda item: item.score, reverse=True)
        if ranked and ranked[0].score >= self.auto_accept_threshold:
            margin = ranked[0].score - (ranked[1].score if len(ranked) > 1 else 0)
            if margin >= self.ambiguity_margin:
                return self._resolved(mention, ranked[0], "MODEL_RERANK")
        provisional = KnowledgeEntity(
            canonical_name=mention.mention,
            normalized_name=normalized,
            entity_type=mention.suggested_entity_type.value,
            country_code=mention.country_hint or "",
            resolution_state=ResolutionState.PROVISIONAL if not ranked else ResolutionState.AMBIGUOUS,
            attributes={"ticker_hint": mention.ticker_hint} if mention.ticker_hint else {},
        )
        return ResolvedMention(
            mention_id=mention.mention_id, entity=provisional, confidence=0.5,
            method="PROVISIONAL" if not ranked else "AMBIGUOUS",
        )

    @staticmethod
    def _resolved(mention: EntityMention, candidate: EntityCandidate, method: str) -> ResolvedMention:
        return ResolvedMention(
            mention_id=mention.mention_id,
            entity=candidate.entity,
            security_id=candidate.security_id,
            confidence=candidate.score,
            method=method,
        )

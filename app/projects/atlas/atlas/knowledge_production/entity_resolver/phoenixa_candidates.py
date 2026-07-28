from __future__ import annotations

from uuid import UUID, uuid5

from atlas.core.clients import PhoenixAClient
from atlas.knowledge_production.entity_resolver.name_normalizer import normalize_entity_name
from atlas.models import EntityCandidate, KnowledgeEntity, ResolutionState

SECURITY_ENTITY_NAMESPACE = UUID("4c0a50c5-0192-48ba-8a42-a4bf99939566")


class PhoenixAEntityCandidateSource:
    def __init__(self, client: PhoenixAClient) -> None:
        self.client = client

    async def find_candidates(
        self, normalized_name: str, entity_type: str, ticker_hint: str | None
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        rows = await self.client.search_knowledge_entities(
            normalized_name, entity_type, 20
        )
        exact_match = bool(rows)
        if not rows:
            rows = await self.client.search_knowledge_entities(
                normalized_name,
                entity_type,
                20,
                exact=False,
            )
        for row in rows:
            entity = KnowledgeEntity.model_validate(row)
            candidates.append(EntityCandidate(
                entity=entity,
                score=1.0 if exact_match else 0.7,
                reasons=[
                    "EXACT_KNOWLEDGE_ALIAS"
                    if exact_match
                    else "FUZZY_KNOWLEDGE_NAME"
                ],
            ))
        if entity_type == "COMPANY":
            security_rows = await self.client.search_securities(
                ticker_hint or normalized_name, 20
            )
            items = (
                security_rows.get("items", [])
                if isinstance(security_rows, dict)
                else security_rows
            )
            for row in items:
                security_id = int(row["id"])
                canonical_name = row.get("name") or row.get("symbol") or normalized_name
                security_normalized = normalize_entity_name(canonical_name)
                exact = security_normalized == normalized_name or (
                    ticker_hint and str(row.get("symbol", "")).casefold() == ticker_hint.casefold()
                )
                entity = KnowledgeEntity(
                    id=uuid5(SECURITY_ENTITY_NAMESPACE, str(security_id)),
                    canonical_name=canonical_name,
                    normalized_name=security_normalized,
                    entity_type="COMPANY",
                    country_code="CN",
                    resolution_state=ResolutionState.RESOLVED_SECURITY,
                    attributes={
                        "symbol": row.get("symbol"),
                        "exchange": row.get("exchange"),
                    },
                )
                candidates.append(EntityCandidate(
                    entity=entity,
                    security_id=security_id,
                    score=1.0 if exact else 0.7,
                    reasons=["SECURITY_REGISTRY_EXACT" if exact else "SECURITY_REGISTRY_SEARCH"],
                ))
        deduplicated: dict[object, EntityCandidate] = {}
        for candidate in candidates:
            current = deduplicated.get(candidate.entity.id)
            if current is None or (
                candidate.security_id is not None and current.security_id is None
            ) or candidate.score > current.score:
                deduplicated[candidate.entity.id] = candidate
        return list(deduplicated.values())

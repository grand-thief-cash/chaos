from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from atlas.application.extraction_orchestrator import ExtractionOrchestrator
from atlas.knowledge_production.claim_builder import (
    build_analyst_views,
    build_quantified_claims,
    build_relation_claims,
)
from atlas.knowledge_production.entity_resolver import (
    EntityClusterer,
    EntityResolutionService,
)
from atlas.knowledge_production.entity_resolver.name_normalizer import (
    normalize_entity_name,
)
from atlas.knowledge_store.graph_projection import is_projectable
from atlas.models import (
    AnalystView,
    ExtractionRun,
    ExtractionRunStatus,
    KnowledgeEntity,
    KnowledgeEntityAlias,
    QuantifiedClaim,
    RelationClaim,
    ResearchReport,
)


def _normalize_alias(value: str) -> str:
    return normalize_entity_name(value)


class KnowledgeProductionStore(Protocol):
    async def update_extraction_run(self, run: ExtractionRun) -> None: ...

    async def upsert_knowledge_entities(
        self, entities: list[KnowledgeEntity]
    ) -> None: ...

    async def upsert_security_entity_links(
        self, links: list[dict]
    ) -> None: ...

    async def upsert_entity_aliases(
        self, aliases: list[KnowledgeEntityAlias]
    ) -> None: ...

    async def upsert_claims(
        self,
        relations: list[RelationClaim],
        quantified: list[QuantifiedClaim],
        views: list[AnalystView],
    ) -> None: ...

    async def project_graph(
        self, entities: list[KnowledgeEntity], claims: list[RelationClaim]
    ) -> None: ...


class KnowledgeProductionOrchestrator:
    """Turns one validated extraction into governed relational and graph records."""

    def __init__(
        self,
        extraction: ExtractionOrchestrator,
        resolver: EntityResolutionService,
        store: KnowledgeProductionStore,
        clusterer: EntityClusterer | None = None,
    ) -> None:
        self.extraction = extraction
        self.resolver = resolver
        self.store = store
        self.clusterer = clusterer

    @property
    def pipeline_version(self) -> str:
        return self.extraction.pipeline_version

    async def run_document(
        self,
        report: ResearchReport,
        *,
        semantic_config: dict,
        report_profile: dict,
        force: bool = False,
    ) -> ExtractionRun:
        outcome = await self.extraction.run_document_with_result(
            report,
            semantic_config=semantic_config,
            report_profile=report_profile,
            force=force,
            finalize_status=False,
        )
        if outcome.result is None:
            return outcome.run
        run = outcome.run
        run.status = ExtractionRunStatus.PROCESSING
        run.completed_at = None
        await self.store.update_extraction_run(run)
        try:
            resolutions = await self._resolve_mentions(
                outcome.result.entity_mentions
            )
            entities = list({
                resolution.entity.id: resolution.entity
                for resolution in resolutions
            }.values())
            security_links = [
                {
                    "entity_id": str(resolution.entity.id),
                    "security_id": resolution.security_id,
                    "confidence": resolution.confidence,
                    "resolution_method": resolution.method,
                }
                for resolution in resolutions
                if resolution.security_id is not None
            ]
            security_links = list({
                item["entity_id"]: item for item in security_links
            }.values())
            mentions_by_id = {
                mention.mention_id: mention
                for mention in outcome.result.entity_mentions
            }
            aliases_by_key = {}
            for resolution in resolutions:
                mention = mentions_by_id[resolution.mention_id]
                normalized_alias = _normalize_alias(mention.mention)
                aliases_by_key[
                    (resolution.entity.id, normalized_alias)
                ] = KnowledgeEntityAlias(
                    entity_id=resolution.entity.id,
                    alias=mention.mention,
                    normalized_alias=normalized_alias,
                    source=f"REPORT_{report.source.upper()}"[:64],
                )
            aliases = list(aliases_by_key.values())

            relation_claims = build_relation_claims(
                outcome.result, resolutions, semantic_config
            )
            quantified_claims = build_quantified_claims(
                outcome.result, resolutions
            )
            analyst_views = build_analyst_views(
                outcome.result, resolutions
            )

            await self.store.upsert_knowledge_entities(entities)
            await self.store.upsert_entity_aliases(aliases)
            await self.store.upsert_security_entity_links(security_links)
            await self.store.upsert_claims(
                relation_claims, quantified_claims, analyst_views
            )

            projectable = [
                claim for claim in relation_claims if is_projectable(claim)
            ]
            if projectable:
                projected_entity_ids = {
                    entity_id
                    for claim in projectable
                    for entity_id in (
                        claim.subject_entity_id,
                        claim.object_entity_id,
                    )
                }
                await self.store.project_graph(
                    [
                        entity
                        for entity in entities
                        if entity.id in projected_entity_ids
                    ],
                    projectable,
                )
            run.status = ExtractionRunStatus.SUCCEEDED
            run.error_code = None
            run.error_summary = None
        except Exception as exc:
            run.status = ExtractionRunStatus.FAILED_RETRYABLE
            run.error_code = "KNOWLEDGE_PRODUCTION_FAILED"
            run.error_summary = str(exc)[:2000]
        finally:
            run.completed_at = datetime.now(UTC)
            await self.store.update_extraction_run(run)
        return run

    async def _resolve_mentions(self, mentions):
        if self.clusterer is None:
            return [
                await self.resolver.resolve(mention)
                for mention in mentions
            ]
        by_id = {mention.mention_id: mention for mention in mentions}
        clusters = await self.clusterer.cluster(mentions)
        resolutions = []
        for cluster in clusters:
            representative = by_id[cluster.canonical_mention_id]
            resolved = await self.resolver.resolve(representative)
            for mention_id in cluster.mention_ids:
                resolutions.append(
                    resolved.model_copy(update={
                        "mention_id": mention_id,
                        "method": (
                            resolved.method
                            if mention_id == representative.mention_id
                            else f"DOCUMENT_COREFERENCE:{resolved.method}"
                        ),
                    })
                )
        return resolutions

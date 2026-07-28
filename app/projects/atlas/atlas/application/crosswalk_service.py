from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Protocol

from atlas.application.crosswalk_orchestrator import CrosswalkOrchestrator
from atlas.knowledge_production.ontology_discovery import (
    SemanticRegistry,
    SemanticYamlPublisher,
)
from atlas.models import (
    CrosswalkMapping,
    CrosswalkRun,
    CrosswalkValidation,
    MappingRelation,
    TaxonomyCfg,
    TaxonomyNode,
    TaxonomySchemeCfg,
)


class TaxonomyLoader(Protocol):
    async def list_taxonomy_nodes(
        self, scheme_name: str, scheme: TaxonomySchemeCfg
    ) -> list[TaxonomyNode]: ...


class GovernanceWriter(Protocol):
    async def save_governance_record(self, kind: str, payload: dict) -> dict: ...
    async def list_governance_records(self, kind: str, limit: int = 100) -> list[dict]: ...


class CrosswalkSchemeService:
    def __init__(
        self,
        config: TaxonomyCfg,
        loader: TaxonomyLoader,
        writer: GovernanceWriter,
        orchestrator: CrosswalkOrchestrator,
        semantic_registry: SemanticRegistry,
        *,
        semantic_directory: str | Path,
    ) -> None:
        self.config = config
        self.loader = loader
        self.writer = writer
        self.orchestrator = orchestrator
        self.semantic_registry = semantic_registry
        self.publisher = SemanticYamlPublisher(semantic_directory)

    async def run_schemes(self, source_scheme: str, target_scheme: str) -> dict:
        try:
            source_cfg = self.config.schemes[source_scheme]
        except KeyError as exc:
            raise ValueError(f"unknown taxonomy scheme: {exc.args[0]}") from exc
        source_nodes = await self.loader.list_taxonomy_nodes(source_scheme, source_cfg)
        target_nodes = await self._load_target(target_scheme)
        if not source_nodes or not target_nodes:
            raise ValueError("source and target taxonomies must both contain nodes")
        if (
            source_scheme == self.config.canonical_seed_scheme
            and target_scheme == "ATLAS_CANONICAL"
        ):
            run = self._seed_canonical(source_nodes, target_nodes)
        else:
            run = await self.orchestrator.run(source_nodes, target_nodes)
        payload = run.model_dump(mode="json")
        await self.writer.save_governance_record("crosswalk", payload)
        return payload

    async def run_required(self) -> list[dict]:
        sources = [
            self.config.canonical_seed_scheme,
            *[
                scheme
                for scheme in self.config.schemes
                if scheme != self.config.canonical_seed_scheme
            ],
        ]
        results = [
            await self.run_schemes(source, "ATLAS_CANONICAL")
            for source in sources
        ]
        broker_terms = [
            concept
            for concept in self.semantic_registry.get().concepts
            if concept.concept_type in {"INDUSTRY_CLASS", "VALUE_CHAIN"}
        ]
        if broker_terms:
            target_nodes = await self._load_target("ATLAS_CANONICAL")
            source_nodes = [
                TaxonomyNode(
                    scheme="BROKER_DISCOVERY",
                    code=hashlib.sha256(
                        (
                            concept.concept_type
                            + ":"
                            + concept.canonical_name
                        ).encode("utf-8")
                    ).hexdigest()[:16],
                    name=concept.display_name,
                    level=1,
                    description=concept.description,
                )
                for concept in broker_terms
            ]
            run = await self.orchestrator.run(source_nodes, target_nodes)
            payload = run.model_dump(mode="json")
            await self.writer.save_governance_record(
                "crosswalk", payload
            )
            results.append(payload)
        return results

    async def review(self, run_id: str, payload: dict) -> dict:
        run = CrosswalkRun.model_validate({
            **payload,
            "run_id": run_id,
            "status": "REVIEWED",
        })
        if not run.validation.valid:
            raise ValueError("invalid crosswalk cannot be reviewed for publication")
        result = run.model_dump(mode="json")
        await self.writer.save_governance_record("crosswalk", result)
        return result

    async def publish(self, run_id: str, version: str) -> dict:
        records = await self.writer.list_governance_records("crosswalk")
        payload = next(
            (
                item.get("payload", item)
                for item in records
                if str(item.get("id") or item.get("payload", {}).get("run_id"))
                == run_id
            ),
            None,
        )
        if payload is None:
            raise KeyError(f"crosswalk run not found: {run_id}")
        run = CrosswalkRun.model_validate(payload)
        if run.status != "REVIEWED" or not run.validation.valid:
            raise ValueError("crosswalk must be valid and reviewed before publication")
        base = self.semantic_registry.get()
        published = base.model_copy(deep=True)
        published.version = version
        published.industry_crosswalks = [
            *base.industry_crosswalks,
            run,
        ]
        published.metadata = {
            **base.metadata,
            "base_semantic_version": base.version,
            "crosswalk_run_id": str(run.run_id),
        }
        path = self.publisher.publish(published)
        result = published.model_dump(mode="json")
        await self.writer.save_governance_record("semantic-version", result)
        return {"semantic_version": result, "yaml_path": str(path)}

    async def _load_target(self, target_scheme: str) -> list[TaxonomyNode]:
        if target_scheme != "ATLAS_CANONICAL":
            try:
                target_cfg = self.config.schemes[target_scheme]
            except KeyError as exc:
                raise ValueError(
                    f"unknown taxonomy scheme: {exc.args[0]}"
                ) from exc
            return await self.loader.list_taxonomy_nodes(
                target_scheme, target_cfg
            )
        seed_name = self.config.canonical_seed_scheme
        try:
            seed_cfg = self.config.schemes[seed_name]
        except KeyError as exc:
            raise ValueError(
                f"canonical seed scheme is not configured: {seed_name}"
            ) from exc
        seed = await self.loader.list_taxonomy_nodes(seed_name, seed_cfg)
        return [
            TaxonomyNode(
                scheme="ATLAS_CANONICAL",
                code=f"{seed_name}:{node.code}",
                name=node.name,
                level=node.level,
                parent_code=(
                    f"{seed_name}:{node.parent_code}"
                    if node.parent_code
                    else None
                ),
                description=node.description,
            )
            for node in seed
        ]

    def _seed_canonical(
        self,
        source_nodes: list[TaxonomyNode],
        target_nodes: list[TaxonomyNode],
    ) -> CrosswalkRun:
        mappings = [
            CrosswalkMapping(
                source_scheme=node.scheme,
                source_code=node.code,
                target_scheme="ATLAS_CANONICAL",
                target_code=f"{node.scheme}:{node.code}",
                relation=MappingRelation.EXACT,
                confidence=1,
                rationale="Canonical V1 is deterministically seeded from this scheme.",
            )
            for node in source_nodes
        ]
        return CrosswalkRun(
            source_scheme=source_nodes[0].scheme,
            target_scheme="ATLAS_CANONICAL",
            mappings=mappings,
            validation=CrosswalkValidation(
                valid=len(mappings) == len(target_nodes),
                source_count=len(source_nodes),
                mapped_source_count=len(mappings),
                coverage_ratio=1,
            ),
            status="READY_FOR_REVIEW",
        )

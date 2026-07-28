from __future__ import annotations

from typing import Protocol

from atlas.knowledge_production.industry_crosswalk import CrosswalkValidator
from atlas.models import CrosswalkMapping, CrosswalkRun, TaxonomyNode


class CrosswalkResolutionModel(Protocol):
    async def map_taxonomies(
        self,
        source_nodes: list[TaxonomyNode],
        target_nodes: list[TaxonomyNode],
        validation_errors: list[str] | None = None,
    ) -> list[CrosswalkMapping]: ...


class CrosswalkOrchestrator:
    def __init__(
        self,
        model: CrosswalkResolutionModel,
        *,
        validator: CrosswalkValidator | None = None,
        maximum_repair_attempts: int = 2,
        source_batch_size: int = 50,
    ) -> None:
        self.model = model
        self.validator = validator or CrosswalkValidator()
        self.maximum_repair_attempts = maximum_repair_attempts
        self.source_batch_size = source_batch_size

    async def run(
        self,
        source_nodes: list[TaxonomyNode],
        target_nodes: list[TaxonomyNode],
    ) -> CrosswalkRun:
        errors: list[str] | None = None
        mappings: list[CrosswalkMapping] = []
        validation = None
        for _ in range(self.maximum_repair_attempts + 1):
            mappings = []
            for start in range(0, len(source_nodes), self.source_batch_size):
                batch = source_nodes[start:start + self.source_batch_size]
                mappings.extend(
                    await self.model.map_taxonomies(batch, target_nodes, errors)
                )
            validation = self.validator.validate(source_nodes, target_nodes, mappings)
            if validation.valid:
                break
            errors = validation.errors
        assert validation is not None
        return CrosswalkRun(
            source_scheme=source_nodes[0].scheme if source_nodes else "",
            target_scheme=target_nodes[0].scheme if target_nodes else "",
            mappings=mappings,
            validation=validation,
            status="READY_FOR_REVIEW" if validation.valid else "MODEL_REPAIR_EXHAUSTED",
        )

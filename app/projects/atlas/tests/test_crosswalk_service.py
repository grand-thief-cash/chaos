import pytest

from atlas.application import CrosswalkSchemeService
from atlas.knowledge_production.ontology_discovery import SemanticRegistry
from atlas.models import (
    CrosswalkMapping,
    CrosswalkRun,
    CrosswalkValidation,
    MappingRelation,
    TaxonomyCfg,
    TaxonomyNode,
    TaxonomySchemeCfg,
)


class Loader:
    async def list_taxonomy_nodes(self, scheme_name, scheme):
        return [TaxonomyNode(scheme=scheme_name, code="1", name=scheme_name, level=1)]


class Writer:
    def __init__(self):
        self.saved = None

    async def save_governance_record(self, kind, payload):
        self.saved = (kind, payload)
        return payload


class Orchestrator:
    async def run(self, source_nodes, target_nodes):
        mapping = CrosswalkMapping(
            source_scheme=source_nodes[0].scheme,
            source_code="1",
            target_scheme=target_nodes[0].scheme,
            target_code="1",
            relation=MappingRelation.EXACT,
            confidence=1,
            rationale="same test node",
        )
        return CrosswalkRun(
            source_scheme=source_nodes[0].scheme,
            target_scheme=target_nodes[0].scheme,
            mappings=[mapping],
            validation=CrosswalkValidation(
                valid=True, source_count=1, mapped_source_count=1, coverage_ratio=1
            ),
            status="READY_FOR_REVIEW",
        )


@pytest.mark.asyncio
async def test_crosswalk_scheme_service_loads_runs_and_persists(tmp_path):
    config = TaxonomyCfg(schemes={
        "A": TaxonomySchemeCfg(source="a", taxonomy="industry"),
        "B": TaxonomySchemeCfg(source="b", taxonomy="industry"),
    })
    writer = Writer()
    service = CrosswalkSchemeService(
        config,
        Loader(),
        writer,
        Orchestrator(),
        SemanticRegistry("config/semantic/atlas-semantic-v0001.yaml"),
        semantic_directory=tmp_path,
    )  # type: ignore[arg-type]
    result = await service.run_schemes("A", "B")
    assert result["validation"]["valid"] is True
    assert writer.saved[0] == "crosswalk"


@pytest.mark.asyncio
async def test_crosswalk_scheme_service_rejects_unknown_scheme(tmp_path):
    service = CrosswalkSchemeService(
        TaxonomyCfg(),
        Loader(),
        Writer(),
        Orchestrator(),
        SemanticRegistry("config/semantic/atlas-semantic-v0001.yaml"),
        semantic_directory=tmp_path,
    )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown taxonomy"):
        await service.run_schemes("missing", "B")

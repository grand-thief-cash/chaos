from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from atlas.application.extraction_orchestrator import ExtractionOrchestrator
from atlas.knowledge_production.ontology_discovery import (
    DiscoveryAggregator,
    SemanticRegistry,
    SemanticVersionBuilder,
    SemanticYamlPublisher,
    extraction_to_discovery_result,
    stratified_sample,
)
from atlas.models import DiscoveryDocumentResult, DiscoveryRun


class DiscoveryRepository(Protocol):
    async def list_research_reports(self, **kwargs): ...
    async def save_governance_record(self, kind: str, payload: dict) -> dict: ...
    async def list_governance_records(self, kind: str, limit: int = 100) -> list[dict]: ...


class SemanticDiscoveryService:
    DEFAULT_PROMPT_PROFILES = {
        "stock": "company-research-v1",
        "industry": "industry-research-v1",
        "macro": "macro-research-v1",
        "new_stock": "new-stock-research-v1",
        "strategy": "strategy-research-v1",
        "morning_report": "morning-report-v1",
    }

    def __init__(
        self,
        repository: DiscoveryRepository,
        extraction: ExtractionOrchestrator,
        semantic_registry: SemanticRegistry,
        *,
        semantic_directory: str | Path,
    ) -> None:
        self.repository = repository
        self.extraction = extraction
        self.semantic_registry = semantic_registry
        self.aggregator = DiscoveryAggregator()
        self.version_builder = SemanticVersionBuilder()
        self.publisher = SemanticYamlPublisher(semantic_directory)

    async def run(self, request: Any) -> dict:
        reports = await self.repository.list_research_reports(
            report_types=request.report_types,
            published_from=request.published_from,
            published_to=request.published_to,
            limit=max(request.sample_size * 3, request.sample_size),
        )
        sampled = stratified_sample(reports, request.sample_size)
        semantic = self.semantic_registry.get()
        results = []
        for report in sampled:
            profile = semantic.report_profile(report.report_type, allow_disabled=True)
            profile_key = (
                profile.get("prompt_profile_key")
                or self.DEFAULT_PROMPT_PROFILES.get(
                    report.report_type,
                    f"{report.report_type}-discovery-v1",
                )
            )
            outcome = await self.extraction.run_document_with_result(
                report,
                semantic_config=semantic.payload,
                report_profile={
                    **profile,
                    "prompt_profile_key": profile_key,
                    "discovery_mode": True,
                },
            )
            if outcome.result is not None:
                results.append(
                    extraction_to_discovery_result(
                        outcome.result, report.report_type, profile_key
                    )
                )
            else:
                results.append(
                    DiscoveryDocumentResult(
                        document_id=report.document_id,
                        report_type=report.report_type,
                        readable=False,
                        useful_for_graph=False,
                        usefulness_reason=(
                            outcome.run.error_summary
                            or outcome.run.error_code
                            or "PDF extraction did not produce a validated result"
                        ),
                    )
                )
        run = DiscoveryRun(
            requested_sample_size=request.sample_size,
            sampled_document_ids=[item.document_id for item in sampled],
            document_results=results,
            report_type_assessments=self.aggregator.aggregate_report_types(results),
            predicate_proposals=self.aggregator.aggregate_predicates(results),
            concept_proposals=self.aggregator.aggregate_concepts(results),
        )
        payload = run.model_dump(mode="json")
        await self.repository.save_governance_record("discovery", payload)
        return payload

    async def review(self, run_id: str, payload: dict) -> dict:
        reviewed = DiscoveryRun.model_validate({**payload, "run_id": run_id, "status": "REVIEWED"})
        result = reviewed.model_dump(mode="json")
        await self.repository.save_governance_record("discovery", result)
        return result

    async def publish(self, run_id: str, version: str) -> dict:
        records = await self.repository.list_governance_records("discovery")
        payload = next(
            (
                item.get("payload", item)
                for item in records
                if str(item.get("id") or item.get("payload", {}).get("run_id")) == run_id
            ),
            None,
        )
        if payload is None:
            raise KeyError(f"discovery run not found: {run_id}")
        discovery = DiscoveryRun.model_validate(payload)
        if discovery.status != "REVIEWED":
            raise ValueError("discovery run must be reviewed before publication")
        semantic = self.version_builder.build(discovery, version)
        path = self.publisher.publish(semantic)
        result = semantic.model_dump(mode="json")
        await self.repository.save_governance_record("semantic-version", result)
        self.semantic_registry.invalidate()
        return {"semantic_version": result, "yaml_path": str(path)}

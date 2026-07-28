from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from atlas.core.errors import ExtractionValidationError
from atlas.application import ExtractionOrchestrator
from atlas.knowledge_production.extractor import ExtractionValidator, WholePDFExtractor
from atlas.models import ExtractionRun, ResearchReport


def valid_result() -> dict:
    return {
        "schema_version": "atlas-extraction-v2",
        "semantic_version": "atlas-semantic-v1",
        "document_id": "eastmoney:r1",
        "document_assessment": {
            "readability": "READABLE",
            "readability_reason": None,
            "observed_title": "公司深度报告",
            "primary_language": "zh",
            "possible_truncation": False,
            "last_page_referenced": 2,
        },
        "entity_mentions": [
            {
                "mention_id": "m1",
                "mention": "公司A",
                "suggested_entity_type": "COMPANY",
                "context": "公司A生产产品B",
                "attributes": {},
                "page_number": 2,
            },
            {
                "mention_id": "m2",
                "mention": "产品B",
                "suggested_entity_type": "PRODUCT",
                "context": "公司A生产产品B",
                "attributes": {},
                "page_number": 2,
            },
        ],
        "relation_claims": [
            {
                "candidate_id": "r1",
                "subject_mention_id": "m1",
                "subject_mention": "公司A",
                "raw_predicate": "生产",
                "predicate_family": "PRODUCT",
                "canonical_predicate_hint": "PRODUCES",
                "object_mention_id": "m2",
                "object_mention": "产品B",
                "assertion_type": "OBSERVED_FACT",
                "polarity": "AFFIRMED",
                "qualifiers": {},
                "evidence_quote": "公司A生产产品B",
                "page_number": 2,
                "extraction_confidence": 0.9,
            }
        ],
        "quantified_claims": [],
        "analyst_views": [],
        "unknown_semantic_terms": [],
    }


def test_validator_rejects_markdown_and_dangling_references():
    validator = ExtractionValidator()
    with pytest.raises(ExtractionValidationError):
        validator.validate(
            "```json\n{}\n```",
            expected_document_id="eastmoney:r1",
            expected_semantic_version="atlas-semantic-v1",
            expected_title="公司深度报告",
        )
    payload = valid_result()
    with pytest.raises(
        ExtractionValidationError,
        match="CONSTRAINT_PAGE_OUT_OF_RANGE",
    ):
        validator.validate(
            json.dumps(payload, ensure_ascii=False),
            expected_document_id="eastmoney:r1",
            expected_semantic_version="atlas-semantic-v1",
            expected_title="公司深度报告",
            maximum_page_number=1,
        )
    payload = valid_result()
    payload["relation_claims"][0]["object_mention_id"] = "missing"
    with pytest.raises(ExtractionValidationError):
        validator.validate(
            json.dumps(payload, ensure_ascii=False),
            expected_document_id="eastmoney:r1",
            expected_semantic_version="atlas-semantic-v1",
            expected_title="公司深度报告",
        )


class FakeLLM:
    model_id = "fake-qwen"

    def __init__(self):
        self.calls = 0

    async def complete_pdf(self, *, prompt: str, pdf: bytes, filename: str) -> str:
        self.calls += 1
        return "not-json" if self.calls == 1 else json.dumps(valid_result(), ensure_ascii=False)


@pytest.mark.asyncio
async def test_extractor_regenerates_complete_result():
    llm = FakeLLM()
    extractor = WholePDFExtractor(llm, maximum_total_attempts=2)
    result, attempts, errors = await extractor.extract(
        pdf=b"pdf",
        filename="r1.pdf",
        document_id="eastmoney:r1",
        title="公司深度报告",
        report_type="stock",
        semantic_config={"version": "atlas-semantic-v1"},
        report_profile={"enabled_for_production": True},
    )
    assert result.relation_claims[0].canonical_predicate_hint == "PRODUCES"
    assert attempts == 2
    assert errors and errors[0].startswith("FORMAT_INVALID_JSON")


@dataclass
class FakeStore:
    runs: list[ExtractionRun] = field(default_factory=list)
    result: dict | None = None

    async def create_extraction_run(self, run: ExtractionRun) -> None:
        self.runs.append(run.model_copy(deep=True))

    async def update_extraction_run(self, run: ExtractionRun) -> None:
        self.runs.append(run.model_copy(deep=True))

    async def save_extraction_result(self, run: ExtractionRun, result: dict) -> None:
        self.result = result


class FakeReader:
    def read(self, object_key: str) -> bytes:
        return b"source"


class FakeUnlocker:
    version = "fake"

    def unlock(self, source: bytes):
        return type("Unlocked", (), {"content": b"unlocked", "page_count": 2, "status": "UNLOCKED_IN_MEMORY"})()


@pytest.mark.asyncio
async def test_orchestrator_persists_only_validated_result():
    store = FakeStore()
    extractor = WholePDFExtractor(FakeLLM(), maximum_total_attempts=2)
    orchestrator = ExtractionOrchestrator(
        reader=FakeReader(),
        store=store,
        extractor=extractor,
        unlocker=FakeUnlocker(),
        pipeline_version="atlas-kg-v1",
    )
    report = ResearchReport(
        source="eastmoney",
        resource_id="r1",
        report_type="stock",
        publish_date="2026-07-01",
        title="公司深度报告",
        org_name="某证券",
        pdf_object_key="r1.pdf",
        status="downloaded",
    )
    run = await orchestrator.run_document(
        report,
        semantic_config={"version": "atlas-semantic-v1"},
        report_profile={"enabled_for_production": True},
    )
    assert run.status == "SUCCEEDED"
    assert store.result is not None
    assert run.relation_claim_count == 1

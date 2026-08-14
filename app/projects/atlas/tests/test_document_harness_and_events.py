import pytest
from fastapi.testclient import TestClient

from atlas.api.http_gateway.routes import create_app
from atlas.core.harness_events import HarnessEventRegistry, harness_context
from atlas.knowledge_production.pdf_preprocessor.document_harness import (
    DocumentParserHarness,
)
from atlas.knowledge_production.pdf_preprocessor.text_extractor import PDFTextPage


class _ActiveRegistry:
    def active_handles(self):
        handle = type("Handle", (), {})()
        handle.run_id = "run-active"
        handle.cronjob_run_id = 42
        handle.identity_key = "n=4;types=stock;from=;to=;seed=0"
        return [handle]


class _SamplingConfig:
    class app_info:
        env = "development"

    class engine:
        class knowledge_engine:
            sampling_enabled = True


def test_active_sampling_route_is_process_local_and_does_not_call_phoenixa():
    runtime = type(
        "Runtime",
        (),
        {
            "config": _SamplingConfig(),
            "sample_task_registry": _ActiveRegistry(),
        },
    )()
    app = create_app(runtime)
    response = TestClient(app).get("/api/v1/atlas-kg/sample-runs/active")
    assert response.status_code == 200
    assert response.json() == {
        "data": [{
            "run_id": "run-active",
            "cronjob_run_id": 42,
            "identity_key": "n=4;types=stock;from=;to=;seed=0",
        }],
        "ephemeral": True,
    }


class _Fallback:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    async def extract_pages(self, _pdf, *, filename):
        self.calls += 1
        assert filename.endswith(".pdf")
        return self.pages


@pytest.mark.asyncio
async def test_document_harness_uses_quality_gated_ocr_in_production_path():
    fallback = _Fallback([
        PDFTextPage(1, "公司主营交换机芯片，产业链上游是晶圆代工，下游是数据中心" * 30)
    ])
    events = HarnessEventRegistry(maximum_events_per_run=50)
    harness = DocumentParserHarness(
        fallback,
        events=events,
        primary_extractor=lambda _pdf, **_kwargs: [PDFTextPage(1, "")],
    )
    with harness_context("run-1", document_id="doc-1", report_type="stock"):
        result = await harness.parse(b"pdf", filename="scan.pdf")

    assert result.parser == "_Fallback"
    assert "PARSER_FALLBACK_USED" in result.quality_issues
    assert fallback.calls == 1
    page = events.list_events("run-1")
    assert any(e["event_type"] == "PARSER_FALLBACK_ACCEPTED" for e in page["events"])


@pytest.mark.asyncio
async def test_document_harness_skips_fallback_for_good_text():
    fallback = _Fallback([PDFTextPage(1, "should not be used")])
    harness = DocumentParserHarness(
        fallback,
        primary_extractor=lambda _pdf, **_kwargs: [
            PDFTextPage(1, "行业产业链供需增长，公司产品技术客户供应商竞争格局" * 30)
        ],
    )
    result = await harness.parse(b"pdf", filename="text.pdf")
    assert result.parser == "pdfplumber"
    assert fallback.calls == 0


def test_harness_event_registry_is_bounded_incremental_and_redacted():
    events = HarnessEventRegistry(maximum_events_per_run=20, maximum_runs=2)
    for index in range(25):
        events.emit(
            run_id="run-1",
            stage="llm.sampling",
            event_type="ATTEMPT",
            message=f"attempt {index}",
            details={
                "key": "must-not-leak",
                "api_key_suffix": "must-not-leak-either",
                "attempt": index,
            },
        )
    page = events.list_events("run-1", after_sequence=0, limit=5)
    assert len(page["events"]) == 5
    assert page["oldest_available_sequence"] == 6
    assert page["truncated"] is True
    assert "key" not in page["events"][0]["details"]
    assert "api_key_suffix" not in page["events"][0]["details"]
    next_page = events.list_events(
        "run-1", after_sequence=page["latest_sequence"], limit=100
    )
    assert next_page["events"][0]["sequence"] == page["latest_sequence"] + 1

    events.start_run("run-2")
    events.start_run("run-3")
    assert events.list_events("run-1")["events"] == []

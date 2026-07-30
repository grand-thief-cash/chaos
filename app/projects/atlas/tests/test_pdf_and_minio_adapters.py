from datetime import datetime, timezone
from io import BytesIO
import json

import pikepdf

import pytest

from atlas.core.clients import MinIOPDFReader, MinIOSampleResultStore
from atlas.knowledge_production.pdf_preprocessor import PikePDFUnlocker
from atlas.models import (
    DiscoveryDocumentResult,
    ExtractionRun,
    ExtractionRunStatus,
    ResearchReport,
)


def test_pikepdf_unlocker_removes_owner_restrictions_in_memory():
    source = BytesIO()
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    pdf.save(
        source,
        encryption=pikepdf.Encryption(
            owner="owner-password",
            user="",
            allow=pikepdf.Permissions(extract=False, modify_other=False),
        ),
    )
    result = PikePDFUnlocker().unlock(source.getvalue())
    assert result.page_count == 1
    assert result.status == "UNLOCKED_IN_MEMORY"
    with pikepdf.Pdf.open(BytesIO(result.content)) as unlocked:
        assert not unlocked.is_encrypted


def test_minio_reader_resolves_configured_and_s3_keys_without_network():
    reader = object.__new__(MinIOPDFReader)
    reader.bucket = "research-report"
    assert reader._resolve("stock/a.pdf") == ("research-report", "stock/a.pdf")
    assert reader._resolve("s3://other/path/a.pdf") == ("other", "path/a.pdf")


@pytest.mark.asyncio
async def test_sample_store_writes_one_review_json_in_date_and_type_folders():
    captured = {}

    class Client:
        def put_object(self, bucket, key, data, length, *, content_type):
            captured.update({
                "bucket": bucket,
                "key": key,
                "body": data.read(length),
                "content_type": content_type,
            })

    report = ResearchReport(
        source="eastmoney",
        resource_id="H3_AP_001",
        report_type="industry",
        publish_date="2026-07-20",
        title="行业研报",
        org_name="券商",
        pdf_object_key="industry/2026/H3_AP_001.pdf",
        status="downloaded",
    )
    run = ExtractionRun(
        source_document_id=report.document_id,
        source_report_type=report.report_type,
        pipeline_version="atlas-kg-v1-zhipu-text",
        model_id="glm-4.7-flash",
        prompt_signature="signature",
        extraction_schema_version="atlas-extraction-v2",
        semantic_version="atlas-semantic-v0001",
        input_mode="TEXT_EXTRACTED",
        status=ExtractionRunStatus.FAILED_RETRYABLE,
        error_code="MODEL_PDF_UNREADABLE",
    )
    discovery = DiscoveryDocumentResult(
        document_id=report.document_id,
        report_type=report.report_type,
        readable=False,
        useful_for_graph=False,
        usefulness_reason="image only",
    )
    store = MinIOSampleResultStore(
        "minio:9000", "access", "secret", "atlas-dev", client=Client()
    )
    key = await store.write(
        discovery_run_id="run-1",
        sampled_at=datetime(2026, 7, 20, 8, 30, tzinfo=timezone.utc),
        report=report,
        extraction_run=run,
        extraction_result=None,
        discovery_result=discovery,
    )
    assert key == "sample_output/20260720/industry/H3_AP_001.json"
    assert captured["bucket"] == "atlas-dev"
    assert captured["content_type"] == "application/json; charset=utf-8"
    payload = json.loads(captured["body"])
    assert payload["schema_version"] == "atlas-sample-output-v1"
    assert payload["extraction_result"] is None
    assert payload["extraction_run"]["error_code"] == "MODEL_PDF_UNREADABLE"
    assert payload["discovery_result"]["sample_output_object_key"] == key

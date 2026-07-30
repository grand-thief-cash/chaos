from __future__ import annotations

import asyncio
from datetime import datetime
from io import BytesIO
import json
from pathlib import PurePosixPath
import re
from typing import Protocol

from atlas.models import (
    DiscoveryDocumentResult,
    ExtractionResult,
    ExtractionRun,
    ResearchReport,
)


class SampleResultStore(Protocol):
    async def write(
        self,
        *,
        discovery_run_id: str,
        sampled_at: datetime,
        report: ResearchReport,
        extraction_run: ExtractionRun,
        extraction_result: ExtractionResult | None,
        discovery_result: DiscoveryDocumentResult,
    ) -> str: ...


class MinIOSampleResultStore:
    """Persist one reviewable JSON envelope immediately after each sampled PDF."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        *,
        prefix: str = "sample_output",
        secure: bool = False,
        client=None,
    ) -> None:
        if not bucket.strip():
            raise ValueError("sample output bucket must not be empty")
        if client is None:
            from minio import Minio

            client = Minio(
                endpoint,
                access_key=access_key or None,
                secret_key=secret_key or None,
                secure=secure,
            )
        self.bucket = bucket
        self.prefix = prefix.strip("/") or "sample_output"
        self._client = client

    @staticmethod
    def _safe_segment(value: str) -> str:
        cleaned = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
        return cleaned or "unknown"

    def object_key(self, report: ResearchReport, sampled_at: datetime) -> str:
        source_name = PurePosixPath(
            report.pdf_object_key.split("?", 1)[0]
        ).stem
        document_name = self._safe_segment(report.resource_id or source_name)
        return "/".join((
            self.prefix,
            sampled_at.strftime("%Y%m%d"),
            self._safe_segment(report.report_type),
            f"{document_name}.json",
        ))

    async def write(
        self,
        *,
        discovery_run_id: str,
        sampled_at: datetime,
        report: ResearchReport,
        extraction_run: ExtractionRun,
        extraction_result: ExtractionResult | None,
        discovery_result: DiscoveryDocumentResult,
    ) -> str:
        object_key = self.object_key(report, sampled_at)
        payload = {
            "schema_version": "atlas-sample-output-v1",
            "discovery_run_id": discovery_run_id,
            "sampled_at": sampled_at.isoformat(),
            "sample_output_object_key": object_key,
            "document": report.model_dump(mode="json"),
            "extraction_run": extraction_run.model_dump(mode="json"),
            "extraction_result": (
                extraction_result.model_dump(mode="json")
                if extraction_result is not None
                else None
            ),
            "discovery_result": discovery_result.model_copy(
                update={"sample_output_object_key": object_key}
            ).model_dump(mode="json"),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        await asyncio.to_thread(self._put, object_key, encoded)
        return object_key

    def _put(self, object_key: str, encoded: bytes) -> None:
        self._client.put_object(
            self.bucket,
            object_key,
            BytesIO(encoded),
            len(encoded),
            content_type="application/json; charset=utf-8",
        )

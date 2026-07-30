from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from atlas.application.extraction_orchestrator import ExtractionOrchestrator
from atlas.core.clients import (
    MinIOPDFReader,
    MinIOSampleResultStore,
    PhoenixAClient,
    ZhipuTextPDFClient,
    build_structured_chat_client,
)
from atlas.core.config_manager import ConfigManager
from atlas.knowledge_production.extractor import PromptBuilder, WholePDFExtractor
from atlas.knowledge_production.ontology_discovery import (
    SemanticRegistry,
    extraction_to_discovery_result,
)
from atlas.knowledge_production.pdf_preprocessor import PikePDFUnlocker
from atlas.models import DiscoveryDocumentResult, ResearchReport


REPORT_TYPES = {
    "stock",
    "industry",
    "macro",
    "new_stock",
    "strategy",
    "morning_report",
}


class ModelProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]
    model: str


class MemoryRunStore:
    def __init__(self) -> None:
        self.runs = {}
        self.results = {}

    async def create_extraction_run(self, run) -> None:
        self.runs[str(run.id)] = run.model_copy(deep=True)

    async def update_extraction_run(self, run) -> None:
        self.runs[str(run.id)] = run.model_copy(deep=True)

    async def save_extraction_result(self, run, result) -> None:
        self.results[str(run.id)] = result

    async def find_reusable_extraction(self, *_args, **_kwargs):
        return None


def infer_report_type(object_key: str) -> str | None:
    for segment in PurePosixPath(object_key).parts:
        normalized = segment.lower().replace("-", "_")
        if normalized in REPORT_TYPES:
            return normalized
    return None


def infer_publish_date(object_key: str, fallback: datetime) -> str:
    match = re.search(r"20\d{2}[-_]?\d{2}[-_]?\d{2}", object_key)
    if match is None:
        return fallback.strftime("%Y-%m-%d")
    raw = match.group(0).replace("_", "").replace("-", "")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live Atlas home smoke test without requiring PhoenixA."
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "config-home.yaml"),
    )
    parser.add_argument("--scan-limit", type=int, default=5000)
    parser.add_argument("--max-types", type=int, default=1)
    parser.add_argument("--types", nargs="+", choices=sorted(REPORT_TYPES))
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--model-timeout", type=float)
    parser.add_argument("--run-model", action="store_true")
    parser.add_argument("--write-sample", action="store_true")
    parser.add_argument("--check-phoenixa", action="store_true")
    parser.add_argument("--skip-model-probe", action="store_true")
    return parser.parse_args()


def scan_pdf_inventory(client, bucket: str, limit: int):
    counts: Counter[str] = Counter()
    candidates = {}
    scanned = 0
    for item in client.list_objects(bucket, recursive=True):
        if scanned >= limit:
            break
        scanned += 1
        if item.is_dir or not item.object_name.lower().endswith(".pdf"):
            continue
        report_type = infer_report_type(item.object_name) or "unknown"
        counts[report_type] += 1
        size = int(item.size or 0)
        if 50_000 <= size <= 5_000_000:
            current = candidates.get(report_type)
            if current is None or size < int(current.size or 0):
                candidates[report_type] = item
    return scanned, counts, candidates


async def run() -> int:
    args = parse_args()
    config = ConfigManager().init_config(
        path=args.config,
        env="development",
    )
    from minio import Minio

    minio = Minio(
        config.minio.endpoint,
        access_key=config.minio.access_key,
        secret_key=config.minio.secret_key,
        secure=config.minio.secure,
    )
    bucket_state = {
        config.minio.bucket: minio.bucket_exists(config.minio.bucket),
        config.minio.sample_bucket: minio.bucket_exists(config.minio.sample_bucket),
    }
    if not all(bucket_state.values()):
        print(json.dumps({"buckets": bucket_state}, ensure_ascii=False))
        return 1

    scanned, counts, candidates = scan_pdf_inventory(
        minio, config.minio.bucket, args.scan_limit
    )
    print(json.dumps({
        "buckets": bucket_state,
        "objects_scanned": scanned,
        "pdf_counts": dict(sorted(counts.items())),
        "candidate_types": sorted(candidates),
    }, ensure_ascii=False))

    exit_code = 0
    if args.check_phoenixa:
        phoenixa = PhoenixAClient(
            config.dept_services.phoenixA.base_url,
            research_report_source=config.engine.knowledge_engine.research_report_source,
            timeout_seconds=config.http_client.timeout_seconds,
            verify_ssl=config.http_client.verify_ssl,
            headers=config.http_client.headers,
        )
        try:
            reports = await phoenixa.list_research_reports(
                report_types=["stock", "industry"],
                limit=2,
            )
            governance_status = "ok"
            try:
                await phoenixa.list_governance_records("discovery", limit=1)
            except httpx.HTTPStatusError as exc:
                governance_status = f"http_{exc.response.status_code}"
                exit_code = 1
            print(json.dumps({
                "phoenixa_base_url": config.dept_services.phoenixA.base_url,
                "research_report_count": len(reports),
                "research_report_types": sorted({item.report_type for item in reports}),
                "atlas_governance_api": governance_status,
            }, ensure_ascii=False))
        finally:
            await phoenixa.close()

    if not args.skip_model_probe:
        agent = build_structured_chat_client(config.llm.agent)
        try:
            try:
                probe = await agent.complete_model(
                    ModelProbe,
                    system_prompt="Return only the requested JSON object.",
                    user_prompt=(
                        'Return {"status":"ok","model":"glm-4.7-flash"}. '
                        "Do not add fields."
                    ),
                )
            except Exception as exc:
                failure = {"type": type(exc).__name__, "message": str(exc)}
                if isinstance(exc, httpx.HTTPStatusError):
                    failure["status_code"] = exc.response.status_code
                    failure["response"] = exc.response.text[:500]
                print(json.dumps({"model_probe_error": failure}, ensure_ascii=False))
                return 1
        finally:
            await agent.close()
        print(json.dumps({"model_probe": probe.model_dump()}, ensure_ascii=False))

    if not args.run_model:
        return exit_code

    semantic = SemanticRegistry(
        config.engine.knowledge_engine.semantic_config_path
    ).get()
    extraction_config = config.llm.extraction
    llm = ZhipuTextPDFClient(
        extraction_config.base_url,
        extraction_config.model,
        api_key=extraction_config.resolved_api_key,
        timeout_seconds=args.model_timeout or extraction_config.timeout_seconds,
        temperature=extraction_config.temperature,
        maximum_output_tokens=extraction_config.maximum_output_tokens,
    )
    orchestrator = ExtractionOrchestrator(
        reader=MinIOPDFReader(
            config.minio.endpoint,
            config.minio.access_key,
            config.minio.secret_key,
            config.minio.bucket,
            secure=config.minio.secure,
        ),
        store=MemoryRunStore(),
        extractor=WholePDFExtractor(
            llm,
            prompt_builder=PromptBuilder(
                config.engine.knowledge_engine.prompt_mapping_path
            ),
            maximum_total_attempts=args.attempts,
        ),
        unlocker=PikePDFUnlocker(),
        pipeline_version=config.engine.knowledge_engine.pipeline_version,
    )
    sample_store = MinIOSampleResultStore(
        config.minio.endpoint,
        config.minio.access_key,
        config.minio.secret_key,
        config.minio.sample_bucket,
        prefix=config.minio.sample_output_prefix,
        secure=config.minio.secure,
    )
    sampled_at = datetime.now().astimezone()
    discovery_run_id = f"live-smoke-{uuid4()}"
    failures = 0
    requested_types = set(args.types or REPORT_TYPES)
    selected = [
        candidates[key]
        for key in sorted(candidates)
        if key in requested_types
    ][:args.max_types]
    if not selected:
        print(json.dumps({"error": "no representative PDFs found"}))
        await llm.close()
        return 1

    for item in selected:
        report_type = infer_report_type(item.object_name)
        resource_id = PurePosixPath(item.object_name).stem
        report = ResearchReport(
            source=config.engine.knowledge_engine.research_report_source,
            resource_id=resource_id,
            report_type=report_type,
            publish_date=infer_publish_date(item.object_name, sampled_at),
            title=resource_id,
            org_name="",
            pdf_object_key=item.object_name,
            status="downloaded",
        )
        profile = semantic.report_profile(report_type, allow_disabled=True)
        profile_key = (
            profile.get("prompt_profile_key")
            or f"{report_type}-discovery-v1"
        )
        outcome = await orchestrator.run_document_with_result(
            report,
            semantic_config=semantic.payload,
            report_profile={
                **profile,
                "prompt_profile_key": profile_key,
                "discovery_mode": True,
            },
            force=True,
        )
        if outcome.result is not None:
            discovery_result = extraction_to_discovery_result(
                outcome.result, report_type, profile_key
            )
        else:
            failures += 1
            discovery_result = DiscoveryDocumentResult(
                document_id=report.document_id,
                report_type=report_type,
                readable=False,
                useful_for_graph=False,
                usefulness_reason=(
                    outcome.run.error_summary
                    or outcome.run.error_code
                    or "live extraction failed"
                ),
            )
        object_key = None
        if args.write_sample:
            object_key = await sample_store.write(
                discovery_run_id=discovery_run_id,
                sampled_at=sampled_at,
                report=report,
                extraction_run=outcome.run,
                extraction_result=outcome.result,
                discovery_result=discovery_result,
            )
        print(json.dumps({
            "report_type": report_type,
            "source_object": item.object_name,
            "source_size": item.size,
            "status": outcome.run.status,
            "error_code": outcome.run.error_code,
            "error_summary": outcome.run.error_summary,
            "request_attempt_count": outcome.run.request_attempt_count,
            "validation_error_codes": outcome.run.validation_error_codes,
            "relation_claim_count": outcome.run.relation_claim_count,
            "quantified_claim_count": outcome.run.quantified_claim_count,
            "analyst_view_count": outcome.run.analyst_view_count,
            "sample_output_object_key": object_key,
        }, ensure_ascii=False, default=str))
    await llm.close()
    return 1 if failures or exit_code else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

"""Rebuild field summaries from persisted free JSON without rerunning PDFs."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

from atlas.application.semantic_discovery_service import SemanticDiscoveryService
from atlas.application.runtime import _build_stage_harness
from atlas.core.clients import (
    OllamaChatClient,
    OpenAICompatiblePDFClient,
    OpenRouterTextPDFClient,
    PhoenixAClient,
    ZhipuTextPDFClient,
)
from atlas.core.config_manager import ConfigManager
from atlas.core.llm import KeyPool
from atlas.knowledge_production.ontology_discovery import FreeFieldReviewSummariser
from atlas.knowledge_production.ontology_discovery.free_field_reviewer import (
    _breadth_first_observations,
    _path_document_index,
)
from atlas.models import ModelProvider
from atlas.models.free_extraction import CategoryFieldReview, FreeExtractionResult


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--config", default="config/config-home.yaml")
    parser.add_argument("--report-types", nargs="*")
    parser.add_argument(
        "--promote-success",
        action="store_true",
        help="mark the run SUCCESS only when every document type has a reviewed category",
    )
    parser.add_argument(
        "--filter-existing",
        action="store_true",
        help="apply deterministic business/evidence guards to the existing summary without an LLM call",
    )
    return parser.parse_args()


def _build_llm(config):
    harness = _build_stage_harness("sampling_review", config, {}, {})
    if harness is not None:
        return harness
    knowledge = config.engine.knowledge_engine
    _, model = config.llm.model_for_role("extraction")
    pool = KeyPool(model.api_keys, total_concurrency=knowledge.llm_concurrency)
    if model.provider == ModelProvider.OLLAMA:
        return OllamaChatClient(model, pool)
    if model.provider == ModelProvider.ZHIPU_TEXT:
        return ZhipuTextPDFClient(model, pool)
    if model.provider == ModelProvider.OPENAI_COMPATIBLE_PDF:
        return OpenAICompatiblePDFClient(model, pool)
    return OpenRouterTextPDFClient(model, pool)


def _summary_field_to_review(field: dict, scope: str) -> dict:
    return {
        "field_name": field.get("field_name"),
        "description": field.get("description") or "字段说明",
        "scope": scope,
        "knowledge_graph_role": field.get("knowledge_graph_role") or "unspecified",
        "value_shape": field.get("value_shape") or field.get("value_type") or "object",
        "applicability": field.get("applicability") or "以原评审为准",
        "rationale": field.get("rationale") or "来自已保存字段评审",
        "priority": field.get("priority") or 3,
        "source_document_ids": field.get("evidence_document_ids") or [],
        "observed_json_paths": field.get("observed_json_paths") or [],
        "example_values": field.get("example_values") or [],
    }


def _evidence_complete(fields: list[dict], scope: str) -> list[dict]:
    """Keep ``--filter-existing`` repeatable after an earlier guard pass."""
    return [
        _summary_field_to_review(field, scope)
        for field in fields
        if field.get("evidence_document_ids") and field.get("observed_json_paths")
    ]


async def main() -> int:
    args = parse_args()
    config = ConfigManager().init_config(args.config)
    knowledge = config.engine.knowledge_engine
    http = config.http_client
    phoenix = PhoenixAClient(
        config.dept_services.phoenixA.base_url,
        research_report_source=knowledge.research_report_source,
        timeout_seconds=http.timeout_seconds,
        verify_ssl=http.verify_ssl,
        headers=http.headers,
    )
    llm = _build_llm(config)
    reviewer = FreeFieldReviewSummariser(
        llm,
        batch_size=knowledge.sampling_field_review_batch_size,
        output_tokens=knowledge.sampling_field_review_output_tokens,
    )

    summaries: dict[str, dict] = {}
    try:
        categories = await phoenix.list_sample_category_results(args.run_id)
        requested_types = set(args.report_types or [])
        if requested_types:
            categories = [
                item for item in categories if item.get("report_type") in requested_types
            ]
        for category in categories:
            report_type = str(category["report_type"])
            full = await phoenix.get_sample_category_result(args.run_id, report_type)
            free_results: list[FreeExtractionResult] = []
            for raw in full.get("raw_results") or []:
                payload = raw.get("free_extraction_result")
                if isinstance(payload, dict):
                    free_results.append(FreeExtractionResult.model_validate(payload))
            if args.filter_existing:
                existing = full.get("field_summary") or {}
                review = CategoryFieldReview.model_validate({
                    "report_type": report_type,
                    "reviewed_document_count": len(free_results),
                    "core_fields": _evidence_complete(
                        existing.get("core_fields") or [], "CORE"
                    ),
                    "conditional_fields": _evidence_complete(
                        existing.get("conditional_fields") or [], "CONDITIONAL"
                    ),
                    "rejected_over_specific_fields": existing.get(
                        "rejected_over_specific_fields"
                    ) or [],
                    "document_type_insights": existing.get("document_type_insights") or [],
                    "coverage_gaps": existing.get("coverage_gaps") or [],
                    "review_notes": existing.get("notes") or "",
                })
                valid_paths = {
                    observation["path"]
                    for result in free_results
                    for observation in _breadth_first_observations(
                        result.content,
                        maximum=reviewer.maximum_observations_per_document,
                    )
                }
                review = reviewer._validate_sources(
                    review,
                    {result.document_id for result in free_results},
                    valid_paths,
                    _path_document_index(
                        free_results,
                        maximum=reviewer.maximum_observations_per_document,
                    ),
                )
            else:
                review = await reviewer.summarise(report_type, free_results)
            summary = SemanticDiscoveryService._field_review_to_summary(
                review,
                sampled_document_count=len(free_results),
                readable_document_count=sum(item.readable for item in free_results),
            )
            await phoenix.update_sample_field_summary(
                args.run_id, report_type, summary
            )
            summaries[report_type] = summary

        documents = await phoenix.list_sample_document_results(args.run_id)
        document_types = {str(item.get("report_type")) for item in documents}
        reviewed_types = set(summaries)
        readable_count = sum(item.get("status") == "SUCCESS" for item in documents)
        success_ratio = readable_count / len(documents) if documents else 0
        complete = (
            bool(documents)
            and document_types <= reviewed_types
            and success_ratio >= knowledge.sampling_minimum_success_ratio
        )
        if args.promote_success and complete:
            await phoenix.update_sample_run_status(
                args.run_id,
                "SUCCESS",
                completed_at=datetime.now(UTC).isoformat(),
                error_code="",
                error_message="",
            )

        print(json.dumps({
            "sample_run_id": args.run_id,
            "reviewed_report_types": sorted(reviewed_types),
            "document_report_types": sorted(document_types),
            "all_document_types_reviewed": document_types <= reviewed_types,
            "success_ratio": success_ratio,
            "promoted_to_success": bool(args.promote_success and complete),
            "field_summaries": summaries,
        }, ensure_ascii=False, indent=2))
        return 0 if summaries else 2
    finally:
        await phoenix.close()
        close = getattr(llm, "close", None)
        if callable(close):
            await close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

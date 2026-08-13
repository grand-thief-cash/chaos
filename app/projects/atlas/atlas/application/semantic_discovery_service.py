from __future__ import annotations

import asyncio
import json
import logging
import math
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from atlas.application.extraction_orchestrator import ExtractionOrchestrator
from atlas.application.free_extraction_runner import FreeExtractionRunner
from atlas.core.clients import CronjobCallbackClient, SampleResultStore, StructuredChatClient
from atlas.knowledge_production.ontology_discovery import (
    DiscoveryAggregator,
    FreeDiscoverySummariser,
    FreeFieldReviewSummariser,
    SemanticRegistry,
    SemanticVersionBuilder,
    SemanticYamlPublisher,
    extraction_to_discovery_result,
    stratified_sample,
)
from atlas.knowledge_production.ontology_discovery.sampler import infer_report_subtype
from atlas.models import (
    CategoryFieldSummary,
    DiscoveryDocumentResult,
    DiscoveryRun,
    FieldRecommendation,
)
from atlas.models.free_extraction import CategoryFieldReview, FreeExtractionResult

logger = logging.getLogger(__name__)


class DiscoveryRepository(Protocol):
    """Duck-typed repository backed by phoenixA; implements all methods below."""

    async def list_research_reports(self, **kwargs): ...
    async def save_governance_record(self, kind: str, payload: dict) -> dict: ...
    async def list_governance_records(self, kind: str, limit: int = 100) -> list[dict]: ...
    async def update_sample_run_status(self, run_id: str, status: str, **kwargs) -> None: ...
    async def update_sample_run_progress(self, run_id: str, current: int, total: int, message: str | None = None) -> None: ...
    async def create_sample_document_result(self, run_id: str, doc_id: str, document_id: str, report_type: str, extraction_run_id: str, **kwargs) -> dict: ...
    async def update_sample_document_result(self, run_id: str, doc_id: str, status: str, **kwargs) -> None: ...
    async def upsert_sample_category_result(self, run_id: str, report_type: str, raw_results: list[dict], **kwargs) -> dict: ...
    async def update_sample_field_summary(self, run_id: str, report_type: str, field_summary: dict) -> None: ...


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
        sample_catalog: DiscoveryRepository | None = None,
        semantic_directory: str | Path,
        agent_client: StructuredChatClient | None = None,
        cronjob_callback: CronjobCallbackClient | None = None,
        sample_store: SampleResultStore | None = None,
        free_runner: FreeExtractionRunner | None = None,
        free_summariser: FreeDiscoverySummariser | None = None,
        free_field_reviewer: FreeFieldReviewSummariser | None = None,
        document_concurrency: int = 1,
        minimum_success_ratio: float = 0.6,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.sample_catalog = sample_catalog or repository
        self.extraction = extraction
        self.semantic_registry = semantic_registry
        self.aggregator = DiscoveryAggregator()
        self.version_builder = SemanticVersionBuilder()
        self.publisher = SemanticYamlPublisher(semantic_directory)
        self.agent_client = agent_client
        self.cronjob_callback = cronjob_callback
        self.sample_store = sample_store
        self.free_runner = free_runner
        self.free_summariser = free_summariser
        self.free_field_reviewer = free_field_reviewer
        self.document_concurrency = max(1, document_concurrency)
        self.minimum_success_ratio = min(1, max(0, minimum_success_ratio))
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    async def run_sample(
        self,
        sample_run_id: str,
        request: Any,
        *,
        cronjob_run_id: int | None = None,
    ) -> None:
        """Async, concurrent sample run with progress + cronjob callback.

        Persists per-doc results and per-category aggregated JSON to phoenixA,
        runs the 7th summary agent per category, and finalizes the cronjob run.
        Designed to run as a background task; never raises to the caller (errors
        are recorded on the sample_run and reported via cronjob finalize).
        """
        started_at = self._now_iso()
        try:
            await self.repository.update_sample_run_status(
                sample_run_id, "RUNNING", started_at=started_at
            )
            all_mode = request.sample_size == 0
            if all_mode:
                reports = await self.sample_catalog.list_research_reports(
                    report_types=request.report_types,
                    published_from=request.published_from,
                    published_to=request.published_to,
                    limit=5000,
                )
            else:
                # A global LIMIT over several report types can be exhausted by
                # the database's first type, so later requested types never
                # reach the stratified sampler. Fetch a broad candidate pool
                # independently per type. Sampling four reports from only the
                # newest twelve repeatedly selected quarterly-result notes and
                # hid product/supply-chain/technology subtypes. Catalog reads
                # are cheap compared with PDF/LLM work, so optimise for semantic
                # diversity here.
                requested_types = list(dict.fromkeys(request.report_types))
                per_type_limit = max(
                    80,
                    math.ceil(request.sample_size / max(1, len(requested_types))) * 12,
                )
                batches = await asyncio.gather(*(
                    self.sample_catalog.list_research_reports(
                        report_types=[report_type],
                        published_from=request.published_from,
                        published_to=request.published_to,
                        limit=per_type_limit,
                    )
                    for report_type in requested_types
                ))
                reports = [report for batch in batches for report in batch]
            if all_mode:
                sampled = list(reports)
            else:
                sampled = stratified_sample(
                    reports,
                    request.sample_size,
                    seed=getattr(request, "sample_seed", 0),
                )
            total = len(sampled)
            await self._report_progress(sample_run_id, cronjob_run_id, 0, total, "sampling started")

            semantic = self.semantic_registry.get()
            use_free = self.free_runner is not None
            # Each entry: {"report", "run", "free_result", "document_result"}
            results_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
            counter = {"done": 0}
            counter_lock = asyncio.Lock()
            document_semaphore = asyncio.Semaphore(self.document_concurrency)

            async def process_one_inner(report: Any) -> None:
                profile = semantic.report_profile(report.report_type, allow_disabled=True)
                profile_key = (
                    profile.get("prompt_profile_key")
                    or self.DEFAULT_PROMPT_PROFILES.get(
                        report.report_type, f"{report.report_type}-discovery-v1"
                    )
                )
                doc_id = str(uuid4())
                free_result: FreeExtractionResult | None = None
                document_result: DiscoveryDocumentResult | None = None
                if use_free:
                    outcome = await self.free_runner.run_document(
                        report,
                        report_profile={
                            **profile,
                            "prompt_profile_key": profile_key,
                            "sampling_subtype": infer_report_subtype(report),
                        },
                    )
                    run = outcome.run
                    free_result = outcome.result
                    doc_status = (
                        "SUCCESS"
                        if free_result is not None and free_result.readable
                        else "FAILED"
                    )
                else:
                    outcome = await self.extraction.run_document_with_result(
                        report,
                        semantic_config=semantic.payload,
                        report_profile={
                            **profile,
                            "prompt_profile_key": profile_key,
                            "discovery_mode": True,
                        },
                    )
                    run = outcome.run
                    if outcome.result is not None:
                        document_result = extraction_to_discovery_result(
                            outcome.result, report.report_type, profile_key
                        )
                        doc_status = "SUCCESS"
                    else:
                        document_result = DiscoveryDocumentResult(
                            document_id=report.document_id,
                            report_type=report.report_type,
                            readable=False,
                            useful_for_graph=False,
                            usefulness_reason=(
                                run.error_summary
                                or run.error_code
                                or "PDF extraction did not produce a validated result"
                            ),
                        )
                        doc_status = "FAILED"
                doc_started = (
                    run.started_at.isoformat()
                    if run.started_at is not None
                    else self._now_iso()
                )
                doc_completed = (
                    run.completed_at.isoformat()
                    if run.completed_at is not None
                    else self._now_iso()
                )
                duration_ms = self._duration_ms(doc_started, doc_completed)
                await self.repository.create_sample_document_result(
                    sample_run_id, doc_id, report.document_id, report.report_type,
                    extraction_run_id=str(run.id),
                    status=doc_status,
                )
                await self.repository.update_sample_document_result(
                    sample_run_id, doc_id, doc_status,
                    started_at=doc_started, completed_at=doc_completed,
                    duration_ms=duration_ms,
                    error_code=run.error_code,
                    error_message=(run.error_summary or None) if doc_status == "FAILED" else None,
                )
                async with counter_lock:
                    counter["done"] += 1
                    done = counter["done"]
                    results_by_type[report.report_type].append({
                        "report": report,
                        "run": run,
                        "free_result": free_result,
                        "document_result": document_result,
                    })
                    # Checkpoint the category after every paid document. This
                    # intentionally happens before the next model call: a user
                    # pause, process restart, or later reviewer failure can then
                    # reuse all completed free JSON instead of rerunning PDFs.
                    category_items = list(results_by_type[report.report_type])
                    if use_free:
                        checkpoint_raw = [
                            self._build_free_raw_element(
                                item["report"], item["run"], item["free_result"]
                            )
                            for item in category_items
                        ]
                    else:
                        checkpoint_raw = [
                            self._build_raw_element(
                                item["report"], item["run"], item["document_result"]
                            )
                            for item in category_items
                        ]
                    await self.repository.upsert_sample_category_result(
                        sample_run_id,
                        report.report_type,
                        checkpoint_raw,
                        generated_at=self._now_iso(),
                    )
                await self._report_progress(
                    sample_run_id, cronjob_run_id, done, total,
                    f"{report.report_type}: {done}/{total}",
                )

            async def process_one(report: Any) -> None:
                async with document_semaphore:
                    await process_one_inner(report)

            await asyncio.gather(*(process_one(report) for report in sampled))

            # Persist every category's per-document JSON before any LLM review.
            # A reviewer failure in the first category must not discard the
            # already-paid extraction results of later categories.
            all_results: list[DiscoveryDocumentResult] = []
            category_work: dict[str, dict[str, Any]] = {}
            for report_type, items in results_by_type.items():
                if use_free:
                    free_results = [
                        it["free_result"]
                        for it in items
                        if it["free_result"] is not None
                    ]
                    raw_results = [
                        self._build_free_raw_element(
                            it["report"], it["run"], it["free_result"]
                        )
                        for it in items
                    ]
                    doc_results_for_summary: list[DiscoveryDocumentResult] = []
                else:
                    doc_results_for_summary = [
                        it["document_result"] for it in items if it["document_result"] is not None
                    ]
                    all_results.extend(doc_results_for_summary)
                    raw_results = [
                        self._build_raw_element(
                            it["report"], it["run"], it["document_result"]
                        )
                        for it in items
                    ]
                await self.repository.upsert_sample_category_result(
                    sample_run_id,
                    report_type,
                    raw_results,
                    generated_at=self._now_iso(),
                )
                category_work[report_type] = {
                    "free_results": free_results if use_free else [],
                    "doc_results": doc_results_for_summary,
                }

            # Preserve all six requested feeds even when one currently has no
            # source objects. This is a coverage gap; never infer its schema
            # from another report type merely to make the run look complete.
            for report_type in dict.fromkeys(request.report_types):
                if report_type in category_work:
                    continue
                await self.repository.upsert_sample_category_result(
                    sample_run_id,
                    report_type,
                    [],
                    generated_at=self._now_iso(),
                )
                empty_summary = CategoryFieldSummary(
                    report_type=report_type,
                    recommended_fields=[],
                    core_fields=[],
                    conditional_fields=[],
                    coverage_gaps=[
                        "当前采样数据源没有该 report_type 的可用 PDF；禁止借用其他类型字段，待 Artemis 补齐数据后重新采样"
                    ],
                    sampled_document_count=0,
                    readable_document_count=0,
                    review_method="no_documents_available",
                    notes="NO_SOURCE_DOCUMENTS",
                ).model_dump(mode="json")
                await self.repository.update_sample_field_summary(
                    sample_run_id, report_type, empty_summary
                )

            # Only after all raw JSON is durable do the optional semantic pass
            # and the strict cross-document field review.
            for report_type, work in category_work.items():
                free_results = work["free_results"]
                doc_results_for_summary = work["doc_results"]
                if use_free and self.free_summariser is not None:
                    summary = await self.free_summariser.summarise(
                        report_type, free_results
                    )
                    category_doc = self.free_summariser.to_document_result(
                        report_type, free_results, summary
                    )
                    all_results.append(category_doc)
                    doc_results_for_summary = [category_doc]
                await self._report_progress(
                    sample_run_id, cronjob_run_id, total, total,
                    f"{report_type}: summarizing fields",
                )
                if use_free:
                    if self.free_field_reviewer is None:
                        raise RuntimeError("free field reviewer is not configured")
                    field_review = await self.free_field_reviewer.summarise(
                        report_type, free_results
                    )
                    if not (field_review.core_fields or field_review.conditional_fields):
                        raise RuntimeError(
                            f"field reviewer produced no reusable fields for {report_type}"
                        )
                    field_summary = self._field_review_to_summary(
                        field_review,
                        sampled_document_count=len(free_results),
                        readable_document_count=sum(
                            1 for result in free_results if result.readable
                        ),
                    )
                else:
                    field_summary = await self._summarize_category(
                        report_type, doc_results_for_summary
                    )
                await self.repository.update_sample_field_summary(
                    sample_run_id, report_type, field_summary
                )

            # Preserve the existing discovery -> semantic-version governance pipeline.
            # The governance record id is the sample_run_id so the review UI can
            # fetch the per-document raw extraction JSON (sample_category_result)
            # by governance record id without a separate lookup.
            run = DiscoveryRun(
                run_id=UUID(sample_run_id),
                requested_sample_size=total,
                sampled_document_ids=[item.document_id for item in sampled],
                document_results=all_results,
                report_type_assessments=self.aggregator.aggregate_report_types(all_results),
                predicate_proposals=self.aggregator.aggregate_predicates(all_results),
                concept_proposals=self.aggregator.aggregate_concepts(all_results),
            )
            await self.repository.save_governance_record("discovery", run.model_dump(mode="json"))

            success_count = sum(
                1
                for items in results_by_type.values()
                for item in items
                if (
                    item["free_result"] is not None and item["free_result"].readable
                    if use_free
                    else item["document_result"] is not None
                    and item["document_result"].readable
                )
            )
            success_ratio = success_count / total if total else 0
            quality_message = (
                f"sampling quality gate: {success_count}/{total} readable "
                f"({success_ratio:.1%}), required {self.minimum_success_ratio:.1%}"
            )
            quality_passed = total > 0 and success_ratio >= self.minimum_success_ratio
            await self.repository.update_sample_run_status(
                sample_run_id,
                "SUCCESS" if quality_passed else "FAILED",
                completed_at=self._now_iso(),
                error_code=None if quality_passed else "SAMPLE_QUALITY_GATE_FAILED",
                error_message=None if quality_passed else quality_message,
            )
            if self.cronjob_callback is not None:
                if quality_passed:
                    await self.cronjob_callback.finalize_success(
                        cronjob_run_id,
                        body=json.dumps({
                            "sample_run_id": sample_run_id,
                            "document_count": total,
                            "readable_document_count": success_count,
                            "success_ratio": success_ratio,
                        }),
                    )
                else:
                    await self.cronjob_callback.finalize_failed(
                        cronjob_run_id, quality_message
                    )
            logger.info("sample run %s completed: %d documents", sample_run_id, total)
        except Exception as exc:
            logger.exception("sample run %s failed", sample_run_id)
            try:
                await self.repository.update_sample_run_status(
                    sample_run_id, "FAILED",
                    completed_at=self._now_iso(),
                    error_code="SAMPLE_RUN_FAILED",
                    error_message=str(exc)[:2000],
                )
            except Exception:
                logger.exception("failed to mark sample run %s as FAILED", sample_run_id)
            if self.cronjob_callback is not None:
                await self.cronjob_callback.finalize_failed(cronjob_run_id, str(exc)[:2000])

    def _build_raw_element(self, report: Any, outcome: Any, dr: DiscoveryDocumentResult) -> dict:
        """One element of a category's raw_results array: title, s3 path, LLM content."""
        return {
            "document_id": report.document_id,
            "title": report.title,
            "s3_path": report.pdf_object_key,
            "report_type": report.report_type,
            "extraction_run_id": str(outcome.run.id),
            "extraction_result": (
                outcome.result.model_dump(mode="json") if outcome.result is not None else None
            ),
            "discovery_result": dr.model_dump(mode="json"),
        }

    def _build_free_raw_element(
        self, report: Any, run: Any, free_result: FreeExtractionResult | None
    ) -> dict:
        """One element of a category's raw_results array in free-extraction mode.

        The per-PDF free extraction JSON is the unit the summariser reads and
        the unit the review UI shows; there is no strict extraction_result.
        """
        return {
            "document_id": report.document_id,
            "title": report.title,
            "s3_path": report.pdf_object_key,
            "report_type": report.report_type,
            "extraction_run_id": str(run.id),
            "free_extraction_result": (
                free_result.model_dump(mode="json")
                if free_result is not None
                else None
            ),
            "extraction_result": None,
        }

    async def _summarize_category(
        self, report_type: str, doc_results: list[DiscoveryDocumentResult]
    ) -> dict:
        """7th-pass agent: recommend fields for full extraction from sampled proposals."""
        if self.agent_client is None:
            return {"report_type": report_type, "recommended_fields": [], "notes": "agent not configured"}
        predicates = self.aggregator.aggregate_predicates(doc_results)
        concepts = self.aggregator.aggregate_concepts(doc_results)
        summary_input = {
            "report_type": report_type,
            "sampled_document_count": len(doc_results),
            "useful_document_count": sum(1 for d in doc_results if d.useful_for_graph),
            "predicate_proposals": [p.model_dump(mode="json") for p in predicates[:80]],
            "concept_proposals": [c.model_dump(mode="json") for c in concepts[:80]],
        }
        system_prompt = (
            "你是 Atlas 语义发现助手。根据采样文档中提取出的 predicate 与 concept 提案，"
            "为该类研报的全量抽取推荐应当抽取的字段清单。"
            "每个字段给出名称、说明、出现频次和推荐理由。"
        )
        user_prompt = json.dumps(summary_input, ensure_ascii=False, default=str)
        try:
            result = await self.agent_client.complete_model(
                CategoryFieldSummary,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return result.model_copy(update={"report_type": report_type}).model_dump(mode="json")
        except Exception as exc:
            logger.warning("category summary agent failed for %s: %s", report_type, exc)
            return {
                "report_type": report_type,
                "recommended_fields": [],
                "notes": f"summary agent failed: {exc}",
            }

    @staticmethod
    def _field_review_to_summary(
        review: CategoryFieldReview,
        *,
        sampled_document_count: int,
        readable_document_count: int,
    ) -> dict:
        def convert(field) -> FieldRecommendation:
            support = max(1, len(set(field.source_document_ids)))
            return FieldRecommendation(
                field_name=field.field_name,
                description=field.description,
                rationale=field.rationale,
                occurrence_count=support,
                value_type=field.value_shape,
                support_document_count=support,
                applicable_document_count=max(1, readable_document_count),
                support_ratio=(support / readable_document_count if readable_document_count else 0),
                example_values=field.example_values,
                evidence_document_ids=field.source_document_ids,
                scope=field.scope,
                knowledge_graph_role=field.knowledge_graph_role,
                value_shape=field.value_shape,
                applicability=field.applicability,
                observed_json_paths=field.observed_json_paths,
                priority=field.priority,
            )

        core = [convert(field) for field in review.core_fields]
        conditional = [convert(field) for field in review.conditional_fields]
        recommended = sorted(
            core + conditional,
            key=lambda item: (0 if item.scope == "CORE" else 1, item.priority, item.field_name),
        )
        return CategoryFieldSummary(
            report_type=review.report_type,
            recommended_fields=recommended,
            core_fields=core,
            conditional_fields=conditional,
            rejected_over_specific_fields=[
                item.model_dump(mode="json")
                for item in review.rejected_over_specific_fields
            ],
            document_type_insights=review.document_type_insights,
            coverage_gaps=review.coverage_gaps,
            sampled_document_count=sampled_document_count,
            readable_document_count=readable_document_count,
            review_method="llm_cross_document_generalization_v1",
            notes=review.review_notes,
        ).model_dump(mode="json")

    async def _report_progress(
        self,
        sample_run_id: str,
        cronjob_run_id: int | None,
        current: int,
        total: int,
        message: str,
    ) -> None:
        try:
            await self.repository.update_sample_run_progress(
                sample_run_id, current, total, message
            )
        except Exception:
            logger.warning("failed to update sample progress for %s", sample_run_id)
        if self.cronjob_callback is not None:
            await self.cronjob_callback.report_progress(cronjob_run_id, current, total, message)

    @staticmethod
    def _duration_ms(started_at: str, completed_at: str) -> int:
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(completed_at)
            return max(0, int((end - start).total_seconds() * 1000))
        except (ValueError, TypeError):
            return 0

    async def run(self, request: Any) -> dict:
        """Legacy synchronous discovery run (governance-only, no sample-run tracking)."""
        discovery_run_id = uuid4()
        sampled_at = self.clock()
        all_mode = getattr(request, "sample_size", 0) == 0
        fetch_limit = 5000 if all_mode else max(request.sample_size * 3, request.sample_size)
        reports = await self.sample_catalog.list_research_reports(
            report_types=request.report_types,
            published_from=request.published_from,
            published_to=request.published_to,
            limit=fetch_limit,
        )
        if all_mode:
            sampled = list(reports)
        else:
            sampled = stratified_sample(
                reports,
                request.sample_size,
                seed=getattr(request, "sample_seed", 0),
            )
        semantic = self.semantic_registry.get()
        results = []
        for report in sampled:
            profile = semantic.report_profile(report.report_type, allow_disabled=True)
            profile_key = (
                profile.get("prompt_profile_key")
                or self.DEFAULT_PROMPT_PROFILES.get(
                    report.report_type, f"{report.report_type}-discovery-v1"
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
                document_result = extraction_to_discovery_result(
                    outcome.result, report.report_type, profile_key
                )
            else:
                document_result = DiscoveryDocumentResult(
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
            if self.sample_store is not None:
                document_result.sample_output_object_key = await self.sample_store.write(
                    discovery_run_id=str(discovery_run_id),
                    sampled_at=sampled_at,
                    report=report,
                    extraction_run=outcome.run,
                    extraction_result=outcome.result,
                    discovery_result=document_result,
                )
            results.append(document_result)
        run = DiscoveryRun(
            run_id=discovery_run_id,
            requested_sample_size=len(sampled),
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

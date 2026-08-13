from __future__ import annotations

import json
import logging

from atlas.core.clients import StructuredChatClient
from atlas.models import (
    ConceptProposal,
    DiscoveryDocumentResult,
    PredicateProposal,
)
from atlas.models.free_extraction import (
    CategoryDiscoverySummary,
    FreeExtractionResult,
)

logger = logging.getLogger(__name__)


# Cap how many documents we feed the summariser in a single prompt. Free
# extractions are verbose; too many at once blows the context window and
# hurts predicate quality. When a category has more, we send the first N
# readable ones and note the truncation.
_MAX_DOCS_PER_SUMMARY = 12


class FreeDiscoverySummariser:
    """Derive predicates/concepts for a report type from a batch of free
    extractions, using the agent model.

    Replaces the previous strict-schema aggregation path: instead of forcing
    per-document ``canonical_predicate_hint`` values and deduping them, the
    agent reads every per-PDF JSON and proposes reusable relations directly.
    """

    def __init__(
        self,
        agent_client: StructuredChatClient | None,
        *,
        max_docs_per_summary: int = _MAX_DOCS_PER_SUMMARY,
    ) -> None:
        self.agent_client = agent_client
        self.max_docs_per_summary = max_docs_per_summary

    async def summarise(
        self,
        report_type: str,
        free_results: list[FreeExtractionResult],
        evidence_document_ids: list[str] | None = None,
    ) -> CategoryDiscoverySummary:
        if self.agent_client is None or not free_results:
            return CategoryDiscoverySummary(
                report_type=report_type,
                notes=(
                    "agent not configured"
                    if self.agent_client is None
                    else "no free extraction results to summarise"
                ),
            )
        readable = [r for r in free_results if r.readable]
        truncated = readable[: self.max_docs_per_summary]
        doc_payload = [self._compact(r) for r in truncated]
        system_prompt = (
            "你是 Atlas 语义发现归纳助手。下面是某类研报的多篇自由抽取结果，"
            "每篇的 content 字段是模型按该篇 PDF 内容自由组织的 JSON（结构各不相同）。"
            "请通读这些 content，归纳出该类研报中可复用的关系谓词(predicate)和概念(concept)。"
            "predicate 的 canonical_name 用 UPPER_SNAKE_CASE，给出 display_name、说明、"
            "主体/客体类型建议、别名和出现次数。concept 给出类型、canonical_name、说明、别名。"
            "只根据 content 中的实际内容归纳，不要凭空创造。每个 predicate 的 occurrence_count "
            "反映在多少篇文档中出现过。同时给出该类文档的可读性总结。"
        )
        user_prompt = json.dumps(
            {
                "report_type": report_type,
                "document_count": len(readable),
                "summarised_document_count": len(truncated),
                "truncated": len(readable) > len(truncated),
                "documents": doc_payload,
            },
            ensure_ascii=False,
            default=str,
        )
        try:
            result = await self.agent_client.complete_model(
                CategoryDiscoverySummary,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.warning("discovery summary agent failed for %s: %s", report_type, exc)
            return CategoryDiscoverySummary(
                report_type=report_type,
                notes=f"summary agent failed: {exc}",
            )
        return result.model_copy(update={"report_type": report_type})

    def to_document_result(
        self,
        report_type: str,
        free_results: list[FreeExtractionResult],
        summary: CategoryDiscoverySummary,
    ) -> DiscoveryDocumentResult:
        """Build the canonical DiscoveryDocumentResult for a category.

        Predicates/concepts come from the summariser; readability/usefulness
        come from the underlying free extractions. Evidence document ids are
        the documents actually summarised.
        """
        readable_count = sum(1 for r in free_results if r.readable)
        useful = bool(summary.predicates or summary.concepts)
        evidence_ids = [r.document_id for r in free_results if r.readable]
        predicates = [
            PredicateProposal(
                canonical_name=p.canonical_name,
                display_name=p.display_name,
                description=p.description,
                subject_types=p.subject_types,
                object_types=p.object_types,
                aliases=p.aliases,
                evidence_document_ids=evidence_ids,
                occurrence_count=max(1, p.occurrence_count),
            )
            for p in summary.predicates
        ]
        concepts = [
            ConceptProposal(
                concept_type=c.concept_type,
                canonical_name=c.canonical_name,
                display_name=c.display_name,
                description=c.description,
                aliases=c.aliases,
                evidence_document_ids=evidence_ids,
                occurrence_count=max(1, c.occurrence_count),
            )
            for c in summary.concepts
        ]
        return DiscoveryDocumentResult(
            document_id=f"{report_type}:category",
            report_type=report_type,
            readable=readable_count > 0,
            useful_for_graph=useful,
            usefulness_reason=(
                summary.readability_summary
                or (f"{len(predicates)} predicates, {len(concepts)} concepts proposed")
                if useful
                else "No reusable knowledge was extracted"
            ),
            predicate_proposals=predicates,
            concept_proposals=concepts,
        )

    @staticmethod
    def _compact(result: FreeExtractionResult) -> dict:
        """Trim a free extraction to the fields the summariser needs.

        content is model-decided free-form JSON, so we pass it through as-is
        rather than cherry-picking fixed fields.
        """
        return {
            "document_id": result.document_id,
            "observed_title": result.observed_title,
            "content": result.content,
        }

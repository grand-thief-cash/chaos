"""Audit a persisted Atlas sample run for field-discovery business regressions."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from typing import Any

import httpx

from atlas.knowledge_production.ontology_discovery.free_field_reviewer import (
    _EXCLUDED_EVIDENCE_PATH_RE,
    _breadth_first_observations,
    _compatible_evidence_paths,
)


EXPECTED_REVIEW_METHOD = "llm_cross_document_generalization_v1"
META_FIELD_PATTERN = re.compile(
    r"分析师|执业证书|免责声明|联系(?:电话|方式)|电子?邮箱|研究员证书|"
    r"发布信息|发布日期|发布机构|相关报告|评级说明|^周观点$|^摘要$|^结论$|"
    r"^核心内容$|^研究内容$|^报告标题$|^报告类型$|^关键要点$|^核心观点$|"
    r"^(?:key_points|main_views|summary|overview|section|sections)$",
    re.I,
)
RAW_PATH_NAME_PATTERN = re.compile(r"[.\[\]]")
PERIOD_FIELD_PATTERN = re.compile(r"(?:19|20)\d{2}|(?:[_-]E|[\u4e00-\u9fff]E)$", re.I)
OVER_SPECIFIC_PATTERN = re.compile(
    r"污泥|光伏组件及相关设备|煤炭销售量|(?:处理量|出货量|发运量)$|(?:业务营收|业务毛利率)$"
)
CONDITIONAL_ONLY_PATTERN = re.compile(
    r"关键经营指标|财务|盈利预测|业绩预测|估值|投资建议|投资评级|推荐标的|"
    r"价格|库存|开工率|产量|销量|市场份额"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8086")
    return parser.parse_args()


def audit_category(category: dict[str, Any]) -> dict[str, Any]:
    report_type = str(category.get("report_type") or "unknown")
    raw_results = category.get("raw_results") or []
    summary = category.get("field_summary") or {}
    hard_failures: list[str] = []
    warnings: list[str] = []
    documents: list[dict[str, Any]] = []

    document_ids = {
        str(item.get("document_id")) for item in raw_results if item.get("document_id")
    }
    path_document_ids: dict[str, set[str]] = {}
    readable_count = 0
    for item in raw_results:
        free = item.get("free_extraction_result") or {}
        content = free.get("content") or {}
        document_id = str(item.get("document_id") or "")
        if document_id and isinstance(content, dict):
            # Evidence validation uses the reviewer's larger path index, not
            # the compact 18 observations sent to each LLM batch. A valid
            # lower-priority path must not fail audit merely because it fell
            # outside the prompt summary window.
            for observation in _breadth_first_observations(content, maximum=200):
                path_document_ids.setdefault(observation["path"], set()).add(document_id)
        title = str(item.get("title") or item.get("document_id") or "unknown")
        readable = str(free.get("readability") or "").upper() == "READABLE" and bool(content)
        if readable:
            readable_count += 1
        if "candidate_fields" in content:
            hard_failures.append(f"{title}: still uses legacy candidate_fields output")
        if not readable:
            warnings.append(f"{title}: free JSON is unreadable or empty")
        quality_issues = list(free.get("quality_issues") or [])
        if quality_issues:
            warnings.append(f"{title}: quality issues = {quality_issues}")
        documents.append({
            "document_id": item.get("document_id"),
            "title": title,
            "readable": readable,
            "top_level_keys": list(content)[:16] if isinstance(content, dict) else [],
            "json_characters": len(json.dumps(content, ensure_ascii=False)),
            "quality_issues": quality_issues,
        })

    if not raw_results:
        hard_failures.append("category has no sampled documents")
    elif readable_count == 0:
        hard_failures.append("category has no readable free document JSON")

    if summary.get("review_method") != EXPECTED_REVIEW_METHOD:
        hard_failures.append(
            f"unexpected review_method={summary.get('review_method')!r}; "
            "cross-document LLM generalization did not run"
        )

    core = summary.get("core_fields") or []
    conditional = summary.get("conditional_fields") or []
    if not core and not conditional:
        hard_failures.append("reviewer produced no reusable fields")
    if len(core) > 8 or len(conditional) > 8 or len(core) + len(conditional) > 12:
        hard_failures.append("reviewer exceeded the 8-per-scope / 12-total field budget")
    if len(document_ids) < 2 and core:
        hard_failures.append(
            "single-document category promoted provisional fields to CORE"
        )

    normalized_names: set[str] = set()
    audited_fields: list[dict[str, Any]] = []
    for expected_scope, fields in (("CORE", core), ("CONDITIONAL", conditional)):
        for field in fields:
            name = str(field.get("field_name") or "").strip()
            normalized = "".join(char.casefold() for char in name if char.isalnum())
            if not name:
                hard_failures.append(f"{expected_scope}: empty field name")
                continue
            if normalized in normalized_names:
                hard_failures.append(f"duplicate generalized field: {name}")
            normalized_names.add(normalized)
            if PERIOD_FIELD_PATTERN.search(name):
                hard_failures.append(f"period/table suffix leaked into field name: {name}")
            if RAW_PATH_NAME_PATTERN.search(name):
                hard_failures.append(f"raw JSON path leaked into field name: {name}")
            if META_FIELD_PATTERN.search(name):
                hard_failures.append(f"low-value report metadata recommended as KG field: {name}")
            if OVER_SPECIFIC_PATTERN.search(name):
                warnings.append(f"review manually for over-specific field: {name}")
            if expected_scope == "CORE" and CONDITIONAL_ONLY_PATTERN.search(name):
                hard_failures.append(f"optional/subtype-specific field leaked into CORE: {name}")
            if name in {"市场概况", "行业概况", "公司概况"}:
                warnings.append(f"generic object may hide graph relationships: {name}")

            sources = set(field.get("evidence_document_ids") or [])
            paths = field.get("observed_json_paths") or []
            if not sources or not sources <= document_ids:
                hard_failures.append(f"{name}: missing or invalid source document IDs")
            if expected_scope == "CORE" and len(sources) < 2:
                hard_failures.append(
                    f"{name}: CORE field lacks cross-document evidence"
                )
            if not paths:
                hard_failures.append(f"{name}: missing observed JSON paths")
            compatible_paths = [
                path for path in _compatible_evidence_paths(name, paths)
                if not _EXCLUDED_EVIDENCE_PATH_RE.search(path)
            ]
            if paths and not compatible_paths:
                hard_failures.append(f"{name}: cited paths are semantically incompatible")
            linked_sources = {
                document_id
                for path in compatible_paths
                for document_id in path_document_ids.get(path, set())
            }
            if sources and not sources <= linked_sources:
                hard_failures.append(
                    f"{name}: source IDs are not linked to the cited JSON paths"
                )
            if str(field.get("scope") or "") != expected_scope:
                hard_failures.append(f"{name}: scope does not match {expected_scope} list")
            audited_fields.append({
                "field_name": name,
                "scope": expected_scope,
                "priority": field.get("priority"),
                "knowledge_graph_role": field.get("knowledge_graph_role"),
                "value_shape": field.get("value_shape"),
                "source_document_count": len(sources),
            })

    for item in summary.get("rejected_over_specific_fields") or []:
        name = str(item.get("observed_field") or "unknown")
        sources = set(item.get("source_document_ids") or [])
        if not sources or not sources <= document_ids:
            hard_failures.append(f"rejected field {name}: missing or invalid source IDs")

    return {
        "report_type": report_type,
        "passed": not hard_failures,
        "document_count": len(raw_results),
        "readable_document_count": readable_count,
        "documents": documents,
        "fields": audited_fields,
        "rejected_over_specific_fields": summary.get("rejected_over_specific_fields") or [],
        "document_type_insights": summary.get("document_type_insights") or [],
        "coverage_gaps": summary.get("coverage_gaps") or [],
        "hard_failures": hard_failures,
        "warnings": warnings,
    }


async def main() -> int:
    args = parse_args()
    base = args.base_url.rstrip("/") + "/api/v1/atlas-kg"
    async with httpx.AsyncClient(timeout=60) as client:
        run_response = await client.get(f"{base}/sample-runs/{args.run_id}")
        run_response.raise_for_status()
        run = run_response.json()
        categories_response = await client.get(
            f"{base}/sample-runs/{args.run_id}/category-results"
        )
        categories_response.raise_for_status()
        category_refs = categories_response.json().get("data", [])
        categories = []
        for item in category_refs:
            report_type = item["report_type"]
            response = await client.get(
                f"{base}/sample-runs/{args.run_id}/category-results/{report_type}"
            )
            response.raise_for_status()
            categories.append(response.json())

    audits = [audit_category(category) for category in categories]
    payload = {
        "sample_run_id": args.run_id,
        "run_status": run.get("status"),
        "passed": run.get("status") == "SUCCESS" and all(item["passed"] for item in audits),
        "categories": audits,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

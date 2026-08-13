"""Build one evidence-backed field catalog from completed sampling runs."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.core.clients import (
    OllamaChatClient,
    OpenAICompatiblePDFClient,
    OpenRouterTextPDFClient,
    PhoenixAClient,
    ZhipuTextPDFClient,
)
from atlas.core.config_manager import ConfigManager
from atlas.core.llm import KeyPool
from atlas.application.runtime import _build_stage_harness
from atlas.knowledge_production.ontology_discovery.free_field_reviewer import (
    _review_json_candidates,
)
from atlas.models import ModelProvider
from atlas.models.free_extraction import SamplingFieldCatalogProposal


CATALOG_PROMPT = """你是产业链知识图谱的总字段架构师。

输入是六类研报经过“逐 PDF 自由 JSON -> 同类多文档评审”后得到的字段。现在从这些已有字段中构造一个供全量抽取使用的主目录；每类必须继续保留自己的 extraction profile。

规则：
1. 合并跨 report_type 的同义字段，例如各类风险合成“关键风险与传导”，各类政策影响合成“政策事件及影响”。
2. 保留产业链实体与关系优先：主营产品/服务、核心技术、产业链定位、上下游、竞争、合作投资、供需与风险传导。
3. 宏观指标、市场信号、投资建议、财务/经营指标等放 CONDITIONAL，并写清 applicable report types/条件；不要为了统一而让所有 PDF 都抽所有字段。
4. 不得创造输入没有的事实或字段来源；source_field_ids 必须逐字来自输入。一个字段可引用多个 source_field_ids。
5. 字段名必须跨公司、跨行业复用，不含公司/产品/年份/单位/_E；不保留“污泥处理量”“光伏组件营收”一类具体指标。
6. 最多 16 个字段。CORE 只是产业链建图的优先语义，不代表每份文档强制有值；缺失时全量抽取应返回 null/[]，不得幻觉。
7. 只返回符合 JSON Schema 的对象。
"""

_BAD_NAME_RE = re.compile(
    r"(?:19|20)\d{2}|[_-]E$|污泥|光伏组件及相关设备|煤炭销售量|"
    r"分析师|免责声明|执业证书|发布日期|发布机构"
)
_CATALOG_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("业务板块与主营产品/服务", re.compile(r"主营产品|主营业务|业务板块|产品/服务")),
    ("关键风险与传导", re.compile(r"关键风险|风险传导|风险因素|风险提示")),
    ("政策事件及影响", re.compile(r"政策事件|政策影响|事件影响")),
    (
        "市场表现与市场信号",
        re.compile(
            r"市场表现|市场信号|市场指数|市场涨跌|海外市场指数|市场供需状况|"
            r"市场热点概念|市场技术分析|市场预期"
        ),
    ),
    ("投资建议与评级", re.compile(r"投资建议|投资评级|建议/评级|行业投资建议")),
    ("关键经营指标", re.compile(r"关键经营指标|经营指标")),
    ("财务与盈利预测", re.compile(r"财务与盈利预测|财务预测|盈利预测")),
    ("宏观经济指标", re.compile(r"宏观经济指标|宏观指标")),
    ("核心技术与研发能力", re.compile(r"核心技术|研发投入与产出|研发能力")),
    ("产能与项目布局", re.compile(r"产能与项目布局|产能布局|项目布局|募投项目")),
    ("产业链定位", re.compile(r"产业链定位|产业链位置")),
    ("上下游关系", re.compile(r"上下游关系|供应关系|客户关系")),
    ("合作与投资", re.compile(r"合作与投资|合作投资")),
    ("竞争格局", re.compile(r"竞争格局|竞争关系")),
    ("供需格局与驱动", re.compile(r"供需格局|供需驱动|供需预期")),
    (
        "产品/技术/应用关系",
        re.compile(r"行业技术应用|行业技术发展路径|产品/技术/应用关系|产品应用关系"),
    ),
)
_REQUIRED_EVIDENCE_BACKED_FAMILIES = {
    "业务板块与主营产品/服务",
    "关键风险与传导",
    "政策事件及影响",
    "关键经营指标",
    "财务与盈利预测",
    "宏观经济指标",
    "核心技术与研发能力",
    "产能与项目布局",
    "产业链定位",
    "上下游关系",
    "合作与投资",
    "竞争格局",
    "供需格局与驱动",
    "产品/技术/应用关系",
    "市场表现与市场信号",
    "投资建议与评级",
}
_CATALOG_CANONICAL_DETAILS: dict[str, tuple[str, str, str, str]] = {
    "业务板块与主营产品/服务": (
        "公司的业务板块、主营产品或服务及其结构",
        "COMPANY_PRODUCES_PRODUCT_OR_SERVICE",
        "[{segment,products_or_services,revenue_share}]",
        "stock 报告披露业务构成或主要供给时",
    ),
    "核心技术与研发能力": (
        "主体掌握的核心技术、研发能力及可验证的创新产出",
        "ENTITY_HAS_TECHNOLOGY_CAPABILITY",
        "[{technology,capability,evidence,application}]",
        "stock、industry 或 strategy 报告出现明确技术/研发证据时",
    ),
    "关键风险与传导": (
        "关键风险、影响对象、传导机制与潜在后果",
        "RISK_AFFECTS_ENTITY",
        "[{risk,affected_entity,mechanism,consequence}]",
        "任一报告披露经营、行业、政策、宏观或市场风险时",
    ),
    "政策事件及影响": (
        "政策或制度事件、作用对象、传导机制与预期影响",
        "POLICY_AFFECTS_ENTITY",
        "[{policy_or_event,target,mechanism,impact,direction}]",
        "报告包含政策、监管或重大制度事件时",
    ),
    "供需格局与驱动": (
        "产品或行业的供给、需求、缺口及其驱动因素",
        "SUPPLY_DEMAND_AFFECTS_ENTITY",
        "[{subject,side,factor,current_state,trend,period}]",
        "industry 或 stock 报告讨论供需、产能、库存或需求驱动时",
    ),
    "关键经营指标": (
        "跨行业承载业务特有的经营量化指标",
        "ENTITY_HAS_OPERATING_METRIC",
        "[{metric_name,period,value,unit,business_segment}]",
        "stock 或 industry 报告披露业务量化指标时",
    ),
    "财务与盈利预测": (
        "历史或预测财务指标的期间、口径、数值、单位与关键假设",
        "ENTITY_HAS_FINANCIAL_METRIC_OR_FORECAST",
        "[{entity,metric,period,value,unit,is_forecast,assumption}]",
        "stock 或 new_stock 报告披露财务数据、盈利预测或估值假设时",
    ),
    "产能与项目布局": (
        "产能、生产基地、在建或募投项目及投产进度",
        "ENTITY_HAS_CAPACITY_OR_PROJECT",
        "[{entity,project_or_base,capacity,unit,status,timeline,location}]",
        "stock、new_stock 或 industry 报告披露产能、基地或项目建设时",
    ),
    "产业链定位": (
        "研究主体在产业链中的环节、角色与定位",
        "ENTITY_HAS_CHAIN_POSITION",
        "[{chain,position,role}]",
        "stock 或 industry 报告有明确产业链环节证据时",
    ),
    "上下游关系": (
        "研究主体与上游投入、供应商、下游应用或客户的关系",
        "ENTITY_HAS_SUPPLY_CHAIN_RELATION",
        "[{direction,entity_or_category,relationship,impact}]",
        "stock 或 industry 报告出现明确供应、客户或应用关系时",
    ),
    "产品/技术/应用关系": (
        "产品、支撑技术与下游应用场景之间的关系",
        "PRODUCT_USES_TECHNOLOGY_FOR_APPLICATION",
        "[{product,technology,application,relationship}]",
        "stock、industry、strategy 或 morning_report 出现直接技术应用证据时",
    ),
    "合作与投资": (
        "主体之间的合作、收购、投资或合资关系及其影响",
        "ENTITY_COOPERATES_OR_INVESTS_IN_ENTITY",
        "[{counterparty,relationship,asset_or_target,impact}]",
        "stock 或 industry 报告披露合作、并购或投资事件时",
    ),
    "宏观经济指标": (
        "财政、货币、增长、通胀、就业或地产等宏观指标",
        "MACRO_INDICATOR",
        "[{metric_name,period,value,unit,change,region}]",
        "macro 报告披露宏观量化指标时",
    ),
    "市场表现与市场信号": (
        "市场、行业或资产表现，以及资金、情绪和技术信号",
        "MARKET_SIGNAL",
        "[{subject,period,signal_type,value,direction}]",
        "industry、morning_report 或 strategy 包含行情/指数/资金信号时",
    ),
    "投资建议与评级": (
        "对行业、公司、资产或配置方向的建议与评级",
        "ANALYST_RECOMMENDS_ENTITY_OR_DIRECTION",
        "[{subject,recommendation,rating,horizon,rationale}]",
        "报告明确给出投资建议、评级或关注方向时",
    ),
    "竞争格局": (
        "研究主体的竞争地位、竞争者、份额或市场集中度",
        "ENTITY_COMPETES_WITH_ENTITY",
        "[{market,entity,competitor,position,market_share}]",
        "stock 或 industry 报告出现明确竞争证据时",
    ),
}


def _catalog_family(name: str) -> str | None:
    for canonical, pattern in _CATALOG_FAMILIES:
        if pattern.search(name):
            return canonical
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_ids", nargs="+")
    parser.add_argument("--config", default="config/config-home.yaml")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--proposal-input",
        type=Path,
        help="reuse a saved reviewer proposal/catalog and skip the LLM call",
    )
    parser.add_argument("--save-governance", action="store_true")
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="skip the optional final LLM pass and merge audited semantic families deterministically",
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


def _parse_proposal(raw: str) -> SamplingFieldCatalogProposal:
    last_error: Exception | None = None
    for value, _recovered in _review_json_candidates(raw):
        try:
            return SamplingFieldCatalogProposal.model_validate(value)
        except Exception as exc:
            last_error = exc
    raise ValueError(f"catalog reviewer returned invalid JSON: {last_error}")


def _deterministic_proposal(sources: dict[str, dict[str, Any]]) -> SamplingFieldCatalogProposal:
    """Safe fallback when a free reviewer ignores the requested schema.

    Category reviews already carry descriptions, shapes and evidence. The
    catalog LLM is useful for synonym selection but must not become a single
    point of failure. This proposal preserves every evidence-backed semantic
    family and lets ``_validate_catalog`` apply the same provenance rules.
    """
    from atlas.models.free_extraction import CatalogFieldProposal

    fields: list[CatalogFieldProposal] = []
    seen: set[str] = set()
    for source_id, source in sources.items():
        name = _catalog_family(str(source.get("field_name") or "")) or str(
            source.get("field_name") or ""
        )
        normalized = "".join(char.casefold() for char in name if char.isalnum())
        if not normalized or normalized in seen or _BAD_NAME_RE.search(name):
            continue
        seen.add(normalized)
        family_ids = [
            candidate_id
            for candidate_id, candidate in sources.items()
            if (_catalog_family(str(candidate.get("field_name") or "")) or candidate.get("field_name"))
            == name
        ]
        fields.append(CatalogFieldProposal(
            field_name=name,
            description=source.get("description") or name,
            scope=source.get("scope") or "CONDITIONAL",
            knowledge_graph_role=source.get("knowledge_graph_role") or "semantic_field",
            value_shape=source.get("value_shape") or "object",
            applicability=source.get("applicability") or "input contains direct evidence",
            priority=3,
            source_field_ids=family_ids[:12] or [source_id],
        ))
        if len(fields) >= 20:
            break
    if not fields:
        raise ValueError("no evidence-backed fields for deterministic catalog fallback")
    return SamplingFieldCatalogProposal(
        fields=fields,
        coverage_gaps=["free catalog reviewer returned incompatible JSON; deterministic evidence-backed fallback used"],
        review_notes="deterministic_catalog_fallback",
    )


def _validate_catalog(
    proposal: SamplingFieldCatalogProposal,
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    proposed_by_family: dict[str, list[Any]] = {}
    passthrough: list[Any] = []
    for field in proposal.fields:
        family = _catalog_family(field.field_name)
        if family:
            proposed_by_family.setdefault(family, []).append(field)
        else:
            passthrough.append(field)

    # Ensure high-value KG families already proven by category review cannot
    # disappear solely because the small final model omitted them.
    for family in _REQUIRED_EVIDENCE_BACKED_FAMILIES:
        if family in proposed_by_family:
            continue
        matching_ids = [
            source_id
            for source_id, source in sources.items()
            if _catalog_family(str(source.get("field_name") or "")) == family
        ]
        if not matching_ids:
            continue
        representative = sources[matching_ids[0]]
        from atlas.models.free_extraction import CatalogFieldProposal

        proposed_by_family[family] = [CatalogFieldProposal(
            field_name=family,
            description=representative.get("description") or family,
            scope=representative.get("scope") or "CONDITIONAL",
            knowledge_graph_role=representative.get("knowledge_graph_role") or family,
            value_shape=representative.get("value_shape") or "object",
            applicability=representative.get("applicability") or "输入存在直接证据时",
            priority=3,
            source_field_ids=matching_ids,
        )]

    candidates: list[tuple[Any, str | None]] = [
        (field, None) for field in passthrough
    ]
    for family, members in proposed_by_family.items():
        base = min(members, key=lambda item: (item.priority, item.field_name))
        candidates.append((base, family))

    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field, family in candidates:
        field_name = family or field.field_name
        normalized = "".join(char.casefold() for char in field_name if char.isalnum())
        family_source_ids = [
            source_id
            for source_id, source in sources.items()
            if family is not None
            and _catalog_family(str(source.get("field_name") or "")) == family
        ]
        requested_ids = [
            source_id for source_id in field.source_field_ids if source_id in sources
        ]
        source_ids = list(dict.fromkeys(family_source_ids + requested_ids))
        if not normalized or normalized in seen or not source_ids or _BAD_NAME_RE.search(field_name):
            continue
        seen.add(normalized)
        source_fields = [sources[source_id] for source_id in source_ids]
        report_types = sorted({item["report_type"] for item in source_fields})
        document_ids = sorted({
            document_id
            for item in source_fields
            for document_id in item["evidence_document_ids"]
        })
        paths = list(dict.fromkeys(
            path
            for item in source_fields
            for path in item["observed_json_paths"]
        ))[:8]
        scope = field.scope
        if len(document_ids) < 2:
            scope = "CONDITIONAL"
        fields.append({
            **field.model_dump(mode="json"),
            "field_name": field_name,
            "scope": scope,
            "source_field_ids": source_ids,
            "applicable_report_types": report_types,
            "evidence_document_ids": document_ids,
            "observed_json_paths": paths,
            "support_document_count": len(document_ids),
            "evidence_grade": (
                "CROSS_DOCUMENT" if len(document_ids) >= 2 else "PROVISIONAL"
            ),
        })
        details = _CATALOG_CANONICAL_DETAILS.get(field_name)
        if details is not None:
            fields[-1].update({
                "description": details[0],
                "knowledge_graph_role": details[1],
                "value_shape": details[2],
                "applicability": details[3],
            })
    fields.sort(key=lambda item: (
        0 if item["scope"] == "CORE" else 1,
        item["priority"],
        item["field_name"],
    ))
    report_types = sorted({
        source["report_type"] for source in sources.values() if source.get("report_type")
    })
    profiles = {
        report_type: [
            {
                key: field[key]
                for key in (
                    "field_name",
                    "scope",
                    "knowledge_graph_role",
                    "value_shape",
                    "applicability",
                    "evidence_grade",
                )
            }
            for field in fields[:16]
            if report_type in field["applicable_report_types"]
        ]
        for report_type in report_types
    }
    provisional_names = [
        field["field_name"] for field in fields[:16]
        if field["evidence_grade"] == "PROVISIONAL"
    ]
    coverage_gaps = list(proposal.coverage_gaps)
    if provisional_names:
        coverage_gaps.append(
            "以下字段当前仅有单文档证据，保留为 PROVISIONAL/CONDITIONAL，需继续扩样："
            + "、".join(provisional_names)
        )
    if not any(field["field_name"] == "产品/技术/应用关系" for field in fields):
        coverage_gaps.append(
            "当前样本尚未形成可通过字段审计的跨行业产品-技术-应用关系证据；需定向扩样"
        )
    return {
        "catalog_version": "sampling-field-catalog-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "fields": fields[:16],
        "coverage_gaps": list(dict.fromkeys(coverage_gaps)),
        "review_notes": proposal.review_notes,
        "extraction_profiles": profiles,
        "core_semantics": (
            "CORE means priority KG semantics when supported by the document; "
            "it is not a required non-null field for every PDF"
        ),
    }


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
    llm = None if args.proposal_input or args.deterministic else _build_llm(config)
    sources: dict[str, dict[str, Any]] = {}
    try:
        for run_id in args.run_ids:
            for category in await phoenix.list_sample_category_results(run_id):
                report_type = str(category["report_type"])
                full = await phoenix.get_sample_category_result(run_id, report_type)
                summary = full.get("field_summary") or {}
                for scope_key in ("core_fields", "conditional_fields"):
                    for field in summary.get(scope_key) or []:
                        source_id = f"{run_id}:{report_type}:{field['field_name']}"
                        sources[source_id] = {
                            "source_field_id": source_id,
                            "report_type": report_type,
                            "field_name": field["field_name"],
                            "scope": field.get("scope"),
                            "description": field.get("description"),
                            "knowledge_graph_role": field.get("knowledge_graph_role"),
                            "value_shape": field.get("value_shape"),
                            "applicability": field.get("applicability"),
                            "support_document_count": field.get("support_document_count"),
                            "evidence_document_ids": field.get("evidence_document_ids") or [],
                            "observed_json_paths": field.get("observed_json_paths") or [],
                        }
        if not sources:
            raise ValueError("no reviewed fields found in the requested sample runs")
        if args.proposal_input:
            proposal = SamplingFieldCatalogProposal.model_validate_json(
                args.proposal_input.read_text(encoding="utf-8")
            )
        elif args.deterministic:
            proposal = _deterministic_proposal(sources)
        else:
            call_kwargs = {
                "prompt": CATALOG_PROMPT,
                "extracted_text": json.dumps(
                    {"reviewed_fields": list(sources.values())},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "filename": "sampling-field-catalog.json",
                "max_tokens": knowledge.sampling_field_review_output_tokens,
                "response_schema": SamplingFieldCatalogProposal.model_json_schema(),
            }
            try:
                complete_validated = getattr(llm, "complete_text_validated", None)
                if callable(complete_validated):
                    raw = await complete_validated(
                        validator=_parse_proposal, **call_kwargs
                    )
                else:
                    raw = await llm.complete_text(**call_kwargs)
                proposal = _parse_proposal(raw)
            except (ValueError, RuntimeError):
                proposal = _deterministic_proposal(sources)
        catalog = _validate_catalog(proposal, sources)
        catalog["source_sample_run_ids"] = args.run_ids
        catalog["source_field_count"] = len(sources)
        if not catalog["fields"]:
            raise ValueError("catalog reviewer produced no evidence-backed fields")
        if args.save_governance:
            saved = await phoenix.save_governance_record("field-catalog", catalog)
            catalog["governance_record"] = saved
        rendered = json.dumps(catalog, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    finally:
        await phoenix.close()
        close = getattr(llm, "close", None) if llm is not None else None
        if callable(close):
            await close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

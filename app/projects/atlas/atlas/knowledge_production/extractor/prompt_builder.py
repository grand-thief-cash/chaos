from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from atlas.models import ExtractionResult


SYSTEM_PROMPT = """你是 Atlas 研报知识抽取器。你只能依据随请求提供的 PDF 或逐页提取文本。
必须遵守：
1. 只返回一个 JSON object，不得返回 Markdown、解释、前后缀或推理过程。
2. PDF 未明确给出的内容不得根据常识补充；宁可留空，也不能猜测。
3. 字段存在信息才填写；缺失时使用 schema 允许的 null、空数组或空对象。
4. 每条 Claim/View 必须有 PDF 中实际出现的最短 evidence_quote 和页码；无法定位时不要抽取。
5. 必须区分已发生事实、公司披露、管理层计划、分析师估计、分析师观点、预测和情景假设。
6. 不得把计划、估计、观点或预测写成 OBSERVED_FACT。
7. ticker、行业代码、数字、单位和日期只有在 PDF 明确出现时才能填写。
8. subject/object 方向必须按 canonical predicate 定义；不确定时 canonical_predicate_hint=null。
9. 若 PDF 正文无法读取，document_assessment.readability=UNREADABLE，并说明原因；不得用空数组伪装可读。
10. 输出必须严格满足 atlas-extraction-v2 schema，禁止额外字段。
11. 不得复述、复制或改写任务描述、Schema、field_dictionary、semantic_config 或 report_profile。
12. 输出顶层必须且只能包含 schema_version、semantic_version、document_id、document_assessment、entity_mentions、relation_claims、quantified_claims、analyst_views、unknown_semantic_terms。"""


FIELD_DICTIONARY = {
    "document_assessment": {
        "readability": "模型是否实际读到了 PDF 正文；不是文档质量评分。",
        "readability_reason": "仅在不可读或内容异常时说明原因。",
        "observed_title": "PDF 内实际看到的标题，用于证明读取的是目标文档。",
        "possible_truncation": "模型怀疑未读完整份 PDF 时为 true。",
        "last_page_referenced": "本次输出引用到的最大 PDF 页码。",
    },
    "entity_mentions": {
        "mention_id": "本次输出内唯一的局部 ID，供 Claim 引用。",
        "mention": "PDF 中出现的原始实体称呼，不要先自行改成数据库名称。",
        "suggested_entity_type": (
            "必须严格选择 COMPANY、PRODUCT、MATERIAL、TECHNOLOGY、MARKET、"
            "INDUSTRY_CLASS、VALUE_CHAIN、ASSET、OTHER 之一；人物、机构或其他"
            "无法准确归类的实体使用 OTHER，不得创造新枚举。"
        ),
        "country_hint": "仅在 PDF 明确表述时填写国家/地区代码。",
        "ticker_hint": "仅在 PDF 明确出现股票代码时填写。",
        "context": "能解释该称呼含义的最短上下文。",
        "attributes": "Schema 未单列但 PDF 明确给出的辅助属性。",
        "page_number": "该称呼证据所在的 PDF 页码。",
    },
    "relation_claims": {
        "candidate_id": "本次输出内唯一的关系候选 ID。",
        "subject_mention_id": "关系主体对应的 mention_id。",
        "raw_predicate": "PDF 原文表达的关系短语。",
        "predicate_family": "关系的宽泛语义族，不等同于 canonical predicate。",
        "canonical_predicate_hint": "生产模式只能选 YAML key；发现模式可建议 UPPER_SNAKE_CASE key。",
        "object_mention_id": "关系客体对应的 mention_id。",
        "assertion_type": "事实、披露、计划、估计、观点、预测或情景假设。",
        "polarity": "AFFIRMED、NEGATED 或 UNCERTAIN；不得省略否定。",
        "qualifiers": "产品、地区、份额等限定条件，不确定则空对象。",
        "valid_from": "PDF 明确给出的关系生效时间；否则 null。",
        "valid_to": "PDF 明确给出的关系结束时间；否则 null。",
        "evidence_quote": "支持该关系的最短逐字原文，不得改写。",
        "page_number": "evidence_quote 所在 PDF 页码。",
        "extraction_confidence": "仅表示模型对抽取/分类的自评，不是真实概率。",
    },
    "quantified_claims": {
        "metric_raw_name": "PDF 使用的原始指标名称。",
        "metric_hint": "可选规范化建议；无把握时 null。",
        "value": "能可靠解析时填写数值，否则 null 并保留 value_text。",
        "value_text": "包含数值、区间、百分比和单位的原始文本。",
        "unit": "PDF 明确给出的单位。",
        "period": "指标对应期间或时点。",
        "change_type": "增加到、增加了、下降到等变化语义。",
        "base_value": "明确存在的基期值。",
        "target_value": "明确存在的目标值。",
        "assertion_type": "必须区分实际经营数据、计划与分析师预测。",
        "evidence_quote": "支持该量化陈述的最短逐字原文。",
    },
    "analyst_views": {
        "view_type_hint": "风险、催化剂、评级逻辑、行业判断等观点类型。",
        "stance": "看多、看空、中性或原文可支持的其他立场。",
        "summary": "忠实压缩后的观点，不得加入 PDF 外信息。",
        "time_horizon": "原文明示的时间尺度。",
        "assertion_type": "通常为 ANALYST_OPINION，也可为 ANALYST_ESTIMATE 或 FORECAST。",
        "evidence_quote": "支持该观点的最短逐字原文。",
    },
    "unknown_semantic_terms": (
        "PDF 中重要但无法映射到当前 predicate/concept YAML 的原始术语；"
        "用于下一版语义发现，不能强行映射。"
    ),
}


class PromptBuilder:
    """Build a versioned, strict extraction prompt from the published semantics."""

    version = "whole-pdf-extraction-v3"

    def __init__(self, mapping_path: str | Path | None = None) -> None:
        self.prompt_profiles: dict[str, dict[str, Any]] = {}
        if mapping_path is not None:
            payload = yaml.safe_load(
                Path(mapping_path).read_text(encoding="utf-8")
            ) or {}
            self.prompt_profiles = payload.get("prompt_profiles", {})

    def resolve_profile(
        self, report_profile: dict[str, Any]
    ) -> dict[str, Any]:
        key = report_profile.get("prompt_profile_key")
        if not key:
            return report_profile
        configured = self.prompt_profiles.get(key)
        if configured is None:
            if report_profile.get("discovery_mode"):
                return {
                    **report_profile,
                    "description": "Generic discovery profile for this report type.",
                }
            raise ValueError(f"unknown production prompt profile: {key}")
        return {
            **configured,
            **report_profile,
        }

    def build(
        self,
        *,
        document_id: str,
        title: str,
        report_type: str,
        semantic_config: dict[str, Any],
        report_profile: dict[str, Any],
        validation_errors: list[str] | None = None,
    ) -> str:
        report_profile = self.resolve_profile(report_profile)
        payload: dict[str, Any] = {
            "task": "extract_atlas_knowledge",
            "document": {
                "document_id": document_id,
                "expected_title": title,
                "report_type": report_type,
            },
            "semantic_config": semantic_config,
            "report_profile": report_profile,
            "field_dictionary": FIELD_DICTIONARY,
            "json_schema": ExtractionResult.model_json_schema(),
            "financial_and_operating_metric_policy": [
                "不要为可由 phoenixA 标准财务报表直接取得或计算的历史收入、利润、ROE、估值比率重复创建知识关系。",
                "保留 PDF 特有且无法从标准财务表直接恢复的经营量化信息，例如产能、产能变化、利用率、市占率、产品价格、订单和项目进度。",
                "保留前瞻财务估计，但必须标记 ANALYST_ESTIMATE 或 FORECAST，不能写成已发生事实。",
            ],
            "required_top_level_fields": [
                "schema_version",
                "semantic_version",
                "document_id",
                "document_assessment",
                "entity_mentions",
                "relation_claims",
                "quantified_claims",
                "analyst_views",
                "unknown_semantic_terms",
            ],
        }
        if report_profile.get("discovery_mode"):
            payload["predicate_constraint"] = (
                "Discovery mode: propose a stable UPPER_SNAKE_CASE "
                "canonical_predicate_hint for a reusable relation even when "
                "it is absent from the current semantic_config. Use null when "
                "the relation meaning or direction is uncertain."
            )
        else:
            payload["predicate_constraint"] = (
                "Production mode: canonical_predicate_hint must be selected "
                "from semantic_config.predicates; otherwise use null."
            )
        if validation_errors:
            payload["previous_output_errors"] = validation_errors
            payload["regeneration_instruction"] = (
                "重新阅读同一 PDF 并完整生成一个新的 JSON，不要局部修补。"
            )
        return SYSTEM_PROMPT + "\n\n" + json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        )

    def signature(
        self,
        semantic_version: str,
        report_profile: dict[str, Any],
        model_id: str,
    ) -> str:
        report_profile = self.resolve_profile(report_profile)
        raw = json.dumps(
            {
                "system_prompt": SYSTEM_PROMPT,
                "prompt_version": self.version,
                "semantic_version": semantic_version,
                "report_profile": report_profile,
                "model_id": model_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

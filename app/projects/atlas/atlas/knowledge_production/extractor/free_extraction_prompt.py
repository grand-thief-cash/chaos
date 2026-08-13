from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


SYSTEM_PROMPT = """你是 Atlas 产业研究文档理解助手。当前处于 sampling/探索阶段，不是在执行固定字段模板。

请自由阅读给定研报内容，并用一个 JSON object 完整表达这篇文档真正有价值的信息。JSON 的层级、key 和组织方式由你依据本篇文档自行决定。

要求：
1. 目标是让没有读过 PDF 的研究人员仅阅读该 JSON，就能理解报告研究对象、主题、核心事实、产业链含义和分析逻辑。
2. 保留具体公司、产品、技术、原材料、客户、供应商、竞争者、上下游、应用场景、产能、市场份额、经营指标、预测、事件、风险等原文信息；文档没有的类别不要硬凑。
3. 按文档自身章节和主题组织内容。禁止只返回 summary/conclusion/key_points/overview/highlights 等空泛通用模板。
4. 具体指标可以保留，因为它们是后续归纳通用字段的观察材料；此阶段不要擅自把所有内容压成统一字段，也不要输出 candidate_fields 数组。
5. 不要拆成孤立的“字段名/值”清单。要保留实体之间、原因与结果之间、业务与上下游之间的语义联系。
6. 可在重要事实旁保留 page/evidence，但不强制每个值都附证据；不要因为少量版面噪声就判不可读。
7. 只返回一个 JSON object，不要 Markdown、解释、状态消息或推理过程。
8. 禁止返回 {"status":"success","message":"任务完成"}。若内容确实无法理解，返回 {"readability":"UNREADABLE","readability_reason":"..."}。
9. 使用文档的主要语言命名 JSON key 和表达内容；中文研报优先使用清晰、自然的中文 key。
10. 输出要信息密集但紧凑。优先保留产业链位置、上下游关系、产品/技术、客户/供应商/竞争者、需求驱动与关键事件；长表格只概括结构和最关键指标，不要逐行照抄资产负债表或预测表。
11. 控制嵌套和数组规模：同类示例保留最有代表性的项目即可，避免因冗长导致 JSON 未闭合。不能为了财务数字而挤掉产业链语义。
"""


MERGE_SYSTEM_PROMPT = """你是 Atlas 研报分段结果整合助手。输入是同一篇 PDF 各页段分别产生的自由 JSON。

请合并为一个连贯、可独立阅读的文档 JSON：
- 仍按这篇文档自身的主题和章节组织，顶层 key 自由决定；
- 合并重复内容，保留不同页段中的重要实体、产业链关系、技术、业务、事件、预测和风险；
- 不要把内容转换为 candidate_fields、统一字段模板或碎片化三元组；
- 不要为了简短而丢失仅在中后段出现的主题；
- 合并时产业链关系、产品技术、客户竞争格局和需求驱动优先于逐年财务表；财务内容保留指标结构与关键结论，不要逐项复制所有表格单元格；
- 输出信息密集、去重、紧凑，并使用文档的主要语言命名 key；
- 不得添加输入 JSON 中不存在的事实；
- 只返回一个 JSON object。
"""


class FreeExtractionPromptBuilder:
    """Build prompts for model-authored per-document sampling JSON."""

    version = "free-document-understanding-v8"

    def __init__(self, mapping_path: str | Path | None = None) -> None:
        self.prompt_profiles: dict[str, dict[str, Any]] = {}
        if mapping_path is not None:
            payload = yaml.safe_load(Path(mapping_path).read_text(encoding="utf-8")) or {}
            self.prompt_profiles = payload.get("prompt_profiles", {})

    def resolve_profile(self, report_profile: dict[str, Any]) -> dict[str, Any]:
        key = report_profile.get("prompt_profile_key")
        if not key:
            return report_profile
        configured = self.prompt_profiles.get(key)
        return report_profile if configured is None else {**configured, **report_profile}

    def build(
        self,
        *,
        document_id: str,
        title: str,
        report_type: str,
        report_profile: dict[str, Any] | None = None,
    ) -> str:
        profile = self.resolve_profile(report_profile or {})
        payload = {
            "document": {
                "document_id": document_id,
                "expected_title": title,
                "report_type": report_type,
                "sampling_subtype_hint": profile.get("sampling_subtype"),
            },
            "instruction": (
                "自由组织一个信息充分、可供研究人员阅读的文档 JSON。"
                "优先保留对产业链知识图谱和后续字段发现有帮助的原始语义，"
                "但不要提前套用固定字段全集。"
            ),
        }
        return SYSTEM_PROMPT + "\n\n" + json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        )

    def build_merge(
        self,
        *,
        document_id: str,
        title: str,
        report_type: str,
        chunk_page_ranges: list[list[int]],
    ) -> str:
        return MERGE_SYSTEM_PROMPT + "\n\n" + json.dumps(
            {
                "document_id": document_id,
                "title": title,
                "report_type": report_type,
                "chunk_page_ranges": chunk_page_ranges,
                "instruction": "合并后直接输出完整文档 JSON。",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def signature(self, report_profile: dict[str, Any], model_id: str) -> str:
        raw = json.dumps(
            {
                "system_prompt": SYSTEM_PROMPT,
                "merge_system_prompt": MERGE_SYSTEM_PROMPT,
                "prompt_version": self.version,
                "report_profile": self.resolve_profile(report_profile),
                "model_id": model_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

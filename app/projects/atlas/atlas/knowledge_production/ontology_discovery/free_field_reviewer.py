from __future__ import annotations

import json
import logging
import re
from collections import deque
from typing import Any, Protocol

from atlas.models.free_extraction import (
    CategoryFieldReview,
    FreeExtractionResult,
    GeneralFieldRecommendation,
)

logger = logging.getLogger(__name__)

_FORCE_CONDITIONAL_RE = re.compile(
    r"关键经营指标|财务|盈利预测|业绩预测|估值|投资建议|投资评级|推荐标的|"
    r"价格|库存|开工率|产量|销量|市场份额|市场表现|行情|涨跌幅|资金流|持仓|"
    r"财政|税收|地方债|货币政策|通胀|就业|房地产|PMI|GDP|进出口|汇率|利率|"
    r"上市条件|减持|退市|分红|基金持仓|资产配置|行业配置|金股"
)
_EXCLUDE_FIELD_RE = re.compile(
    r"分析师|执业证书|免责声明|发布信息|发布日期|发布机构|相关报告|"
    r"联系方式|评级说明|^信息来源$|^数据来源$|^周观点$|^摘要$|^结论$|^核心内容$|^研究内容$|"
    r"^报告标题$|^报告类型$|^事件时间$|^图表信息$|^行业分析$|"
    r"投资评级体系|评级定义|基准指数说明|^关键要点$|^核心观点$|^主要观点$|"
    r"^(?:key_points|main_views|summary|overview|section|sections)$|"
    r"(?:^|\.)(?:date|period|time|year|month|quarter)$|"
    r"(?:^|\.)(?:日期|时间|期间|年份|月份)$"
)
_RAW_JSON_FIELD_NAME_RE = re.compile(r"[.\[\]]|^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$", re.I)
_EXCLUDED_EVIDENCE_PATH_RE = re.compile(
    r"免责声明|分析师|执业证书|发布日期|发布机构|联系方式|评级说明|信息来源|"
    r"数据来源|相关研究|投资评级体系|评级定义|基准指数说明"
)
_FIELD_EVIDENCE_RULES: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(r"产业链定位|产业链位置|所处环节"),
        re.compile(r"产业链定位|产业链位置|所处环节|布局.产业链|上游环节|中游环节|下游环节"),
    ),
    (
        re.compile(r"宏观环境"),
        re.compile(r"宏观|经济|外部环境|国内环境|海外环境|增长|通胀|就业|利率|汇率"),
    ),
    (
        re.compile(r"宏观指标|宏观经济指标"),
        re.compile(
            r"宏观|经济|财政|预算|税收|债务|货币|通胀|就业|房地产|PMI|GDP|"
            r"进出口|汇率|利率|工业企业|企业利润|营业收入|应收账款"
        ),
    ),
    (
        re.compile(r"研究对象|研究主题"),
        re.compile(
            r"研究对象|研究主题|行业名称|研究领域|行业表现|公司名称|公司概况|"
            r"company(?:_name|_profile|_overview)?(?:\.|$)|subject(?:\.|$)",
            re.I,
        ),
    ),
    (
        re.compile(r"产业链|上游|下游|供应关系|客户关系"),
        re.compile(
            r"产业链|上游|中游|下游|供应|客户|原材料|应用|产品|"
            r"industry_chain|upstream|downstream|supplier|customer|application",
            re.I,
        ),
    ),
    (
        re.compile(r"供需"),
        re.compile(r"供需|供应|供给|需求|产能|产量|销量|库存|开工|进口|出口|demand|driver|cyclicality", re.I),
    ),
    (
        re.compile(r"核心技术|技术能力|技术壁垒|技术进展|技术特点|研发壁垒"),
        re.compile(
            r"核心技术|技术优势|技术能力|技术壁垒|技术进展|技术特点|"
            r"研发|专利|工艺|算法|架构|芯片|"
            r"technology|technologies|technical|research_and_development|r_and_d",
            re.I,
        ),
    ),
    (
        re.compile(r"产品应用|应用场景|产品/技术/应用关系|行业技术应用|行业技术发展路径"),
        re.compile(r"技术|产品|应用|模型|芯片|设备|材料"),
    ),
    (
        re.compile(r"主营产品|主营业务|业务板块|业务结构|业务构成"),
        re.compile(
            r"主营|业务|产品|服务|营收|收入|main_business|core_business|"
            r"business_segments?|products?_and_services?|products?_and_technology",
            re.I,
        ),
    ),
    (
        re.compile(r"财务|盈利|估值"),
        re.compile(
            r"财务|营收|收入|利润|净利润|归母|EPS|PE|PB|ROE|毛利|净利|现金流|"
            r"市盈率|市净率|估值|financial|forecast|gross_margin|fair_value|valuation"
            , re.I
        ),
    ),
    (
        re.compile(r"投资建议|投资评级|推荐标的"),
        re.compile(r"投资建议|行业投资建议|评级|推荐|关注方向|布局建议|金股"),
    ),
    (
        re.compile(r"关键经营指标"),
        re.compile(
            r"营收|收入|利润|毛利|净利|产量|销量|产能|处理量|出货|用户|客户|"
            r"份额|金额|发电|供热|装机"
        ),
    ),
    (
        re.compile(r"产能布局"),
        re.compile(r"产能|项目进展|生产线|投产|竣工|装机|基地|在建|并网|capacity|production_base|fundraising_project", re.I),
    ),
    (
        re.compile(r"合作|投资|收购|并购"),
        re.compile(r"合作|投资|收购|并购|入股|合资|股权|标的|交易"),
    ),
    (
        re.compile(
            r"市场表现|行业表现|市场平衡|市场技术指标|海外市场指数|市场涨跌幅|"
            r"市场指数表现|市场供需状况|市场热点概念|市场技术分析|市场预期|行情"
        ),
        re.compile(
            r"市场表现|市场分析|涨跌|收盘|资金流|持仓|指数|估值分位|概念热点|"
            r"技术指标|市场预期|供需状况"
        ),
    ),
    (
        re.compile(r"竞争"),
        re.compile(r"竞争|格局|份额|集中度"),
    ),
    (
        re.compile(r"风险"),
        re.compile(r"风险|不及预期|不确定|挑战|challenge|factors|impact", re.I),
    ),
    (
        re.compile(r"政策|事件影响|操作机制"),
        re.compile(r"政策|事件|法规|条例|贸易|冲突|宏观经济|操作机制|借债"),
    ),
    (
        re.compile(r"价格"),
        re.compile(r"价格|报价|涨价|跌价|价$"),
    ),
)
_FIELD_EVIDENCE_EXCLUSIONS: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(r"关键经营指标"),
        re.compile(r"持股|资金流|涨跌|指数|估值|市场表现|收盘"),
    ),
)


class FreeJSONReviewClient(Protocol):
    model_id: str

    async def complete_text(
        self,
        *,
        prompt: str,
        extracted_text: str,
        filename: str,
        max_tokens: int | None = None,
        response_schema: dict | None = None,
        **kwargs,
    ) -> str: ...


REVIEW_SYSTEM_PROMPT = """你是 Atlas 产业链知识图谱的字段架构评审专家。

输入是同一 report_type 下多篇研报的自由 JSON 摘要观察。你的任务不是复述报告，也不是把每个 JSON key 原样列成字段；而是设计以后可应用于不同公司、不同行业的全量抽取字段。

业务判断规则：
1. 字段必须描述“可复用的语义槽位”，不能把某家公司、产品、年份、单位或表格 E 后缀写进字段名。
2. CORE 只放跨行业产业链图谱普遍有价值的字段，例如主营产品/服务、产业链定位、上游投入与供应关系、下游应用与客户关系、核心技术、竞争关系、产能布局、合作投资、关键风险等。只能根据输入实际出现的语义选择，不要机械照抄这份示例。
   CORE 优先形成可入图的实体和关系：研究对象、产业链参与者及上下游关系、产品/技术/应用关系、供需驱动、竞争格局、政策/事件影响和风险传导。不要用笼统的“市场概况”object 代替输入中已经出现的这些关系。
3. CONDITIONAL 用于确有价值但只适用于特定研报子类/行业的字段，并明确 applicability。行业特有指标不要各自成为模板字段，应上卷为结构化集合，例如“关键经营指标[{指标名,期间,值,单位}]”。
   关键经营指标、财务/盈利预测、估值、投资建议/评级和推荐标的必须放 CONDITIONAL，不能占用产业链 CORE 名额。
   行情/涨跌幅/资金流/持仓，以及财政、货币、通胀、就业、房地产、上市规则等宏观或策略子主题字段也必须放 CONDITIONAL；可归一为“宏观指标”“政策事件”“市场表现”等结构，但不要把某一篇财政报告的字段当作全部 macro 报告的 CORE。
4. “污泥处理量”“煤炭销售量”“光伏组件收入”等是具体事实或指标名，不是跨行业字段；应拒绝或归入更一般的业务板块/关键经营指标结构。
5. “每股收益-最新股本摊薄_E”“2025净利润”之类应归一为带 period/metric/value/unit 的预测或财务指标结构，字段名不得含具体年份或 _E。
6. 对产业链知识图谱价值很弱的格式性字段、分析师证书、免责声明、单一表格列应拒绝。
   分析师信息、发布信息、相关报告以及“周观点/摘要/结论/核心内容”等章节包装 key 也不能成为推荐字段；应读取它们下面的实际业务语义。
7. 输出必须紧凑：core_fields 与 conditional_fields 各最多 8 个、两者合计最多 12 个；description/rationale/applicability 各用一句短句，example_values 最多 2 个，observed_json_paths 最多 3 个。优先少而通用、语义完整，不要为了凑数量创造输入没有支持的字段。
8. source_document_ids 必须来自输入；observed_json_paths 写出促成该建议的原始 JSON 路径。被淘汰的过细字段放 rejected_over_specific_fields，说明 generalized_to 或拒绝原因。
9. 如果输入只有一篇文档，无法证明字段跨文档/跨子类型稳定：可以提出字段，但全部放 CONDITIONAL，并在 coverage_gaps 标记“需要扩样验证”；不要宣布 CORE。
10. 只返回符合 JSON Schema 的对象。
"""


CONSOLIDATE_SYSTEM_PROMPT = """你是 Atlas 产业链知识图谱字段集的终审专家。

输入是若干批次字段评审结果。请合并同义字段、消除重复，重新判断 CORE/CONDITIONAL，保留来源文档与原始路径，并继续拒绝公司/行业过细字段。

终审输入中的 cited_source_observations 给出候选字段所引用 JSON path 的原值。每个字段必须由这些原值直接表达：例如 ETF 净流入不能被泛化为产业供需驱动，风险的影响对象不能单独证明产业链定位。证据语义不直接匹配时删除该字段，不要猜测或补写示例。

终审标准：字段能否作为以后给所有公司/行业研报 LLM 的稳定抽取需求；如果只能适用于某类文档，必须放 CONDITIONAL 并写明 applicability。不要把具体事实、年份、单位、产品名或 _E 表格列当字段。分析师/免责声明/发布信息/相关报告和章节包装 key 必须淘汰。core_fields 与 conditional_fields 各最多 8 个、合计最多 12 个；文字属性各用一句短句，example_values 留空，路径最多 3 个。只返回符合 JSON Schema 的对象。
"""


class FreeFieldReviewSummariser:
    """Hierarchically review free document JSON into reusable extraction fields."""

    def __init__(
        self,
        client: FreeJSONReviewClient | None,
        *,
        batch_size: int = 3,
        maximum_observations_per_document: int = 18,
        output_tokens: int = 2800,
        maximum_attempts: int = 2,
    ) -> None:
        self.client = client
        self.batch_size = max(1, batch_size)
        self.maximum_observations_per_document = max(5, maximum_observations_per_document)
        self.output_tokens = output_tokens
        self.maximum_attempts = max(1, maximum_attempts)

    async def summarise(
        self,
        report_type: str,
        free_results: list[FreeExtractionResult],
    ) -> CategoryFieldReview:
        readable = [result for result in free_results if result.readable]
        if self.client is None or not readable:
            return CategoryFieldReview(
                report_type=report_type,
                reviewed_document_count=len(readable),
                coverage_gaps=[
                    "field review model is not configured"
                    if self.client is None
                    else "no readable free document JSON"
                ],
            )

        compact_documents = {
            result.document_id: self._compact_document(result) for result in readable
        }
        reviews: list[CategoryFieldReview] = []
        for start in range(0, len(readable), self.batch_size):
            batch = readable[start : start + self.batch_size]
            batch_path_documents = _path_document_index(
                batch, maximum=self.maximum_observations_per_document
            )
            payload = {
                "report_type": report_type,
                "review_stage": "documents_to_fields",
                "documents": [compact_documents[result.document_id] for result in batch],
            }
            reviews.append(await self._call_review(
                report_type,
                payload,
                REVIEW_SYSTEM_PROMPT,
                valid_document_ids={result.document_id for result in batch},
                valid_paths={
                    path for path in batch_path_documents
                },
                valid_path_document_ids=batch_path_documents,
            ))

        while len(reviews) > 1:
            next_level: list[CategoryFieldReview] = []
            for start in range(0, len(reviews), 2):
                pair = reviews[start : start + 2]
                if len(pair) == 1:
                    next_level.append(pair[0])
                    continue
                valid_ids = {
                    document_id
                    for review in pair
                    for field in review.core_fields + review.conditional_fields
                    for document_id in field.source_document_ids
                }
                valid_ids.update(
                    document_id
                    for review in pair
                    for rejected in review.rejected_over_specific_fields
                    for document_id in rejected.source_document_ids
                )
                valid_paths = {
                    path
                    for review in pair
                    for field in review.core_fields + review.conditional_fields
                    for path in field.observed_json_paths
                }
                path_document_ids = _path_document_index(
                    [
                        result
                        for result in readable
                        if result.document_id in valid_ids
                    ],
                    maximum=self.maximum_observations_per_document,
                )
                payload = {
                    "report_type": report_type,
                    "review_stage": "field_set_consolidation",
                    "batch_reviews": [self._compact_review(review) for review in pair],
                    "cited_source_observations": _cited_source_observations(
                        pair, compact_documents, maximum=36
                    ),
                }
                next_level.append(await self._call_review(
                    report_type,
                    payload,
                    CONSOLIDATE_SYSTEM_PROMPT,
                    valid_document_ids=valid_ids,
                    valid_paths=valid_paths,
                    valid_path_document_ids={
                        path: document_ids
                        for path, document_ids in path_document_ids.items()
                        if path in valid_paths
                    },
                ))
            reviews = next_level

        final = reviews[0]
        return final.model_copy(update={
            "report_type": report_type,
            "reviewed_document_count": len(readable),
        })

    async def _call_review(
        self,
        report_type: str,
        payload: dict[str, Any],
        system_prompt: str,
        *,
        valid_document_ids: set[str],
        valid_paths: set[str],
        valid_path_document_ids: dict[str, set[str]],
    ) -> CategoryFieldReview:
        last_error: Exception | None = None
        prompt = system_prompt
        for attempt in range(1, self.maximum_attempts + 1):
            try:
                call_kwargs = {
                    "prompt": prompt,
                    "extracted_text": json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":")
                    ),
                    "filename": f"{report_type}-sampling-review.json",
                    "max_tokens": self.output_tokens,
                    "response_schema": CategoryFieldReview.model_json_schema(),
                }

                def validate_raw(candidate: str) -> None:
                    candidate_review, _ = _parse_review_response(candidate)
                    candidate_review = self._validate_sources(
                        candidate_review,
                        valid_document_ids,
                        valid_paths,
                        valid_path_document_ids,
                    )
                    if not (
                        candidate_review.core_fields
                        or candidate_review.conditional_fields
                    ):
                        raise ValueError(
                            "all reviewer fields lacked compatible source evidence"
                        )

                complete_validated = getattr(
                    self.client, "complete_text_validated", None
                )
                if callable(complete_validated):
                    raw = await complete_validated(
                        validator=validate_raw, **call_kwargs
                    )
                else:
                    raw = await self.client.complete_text(**call_kwargs)
                review, recovered = _parse_review_response(raw)
                if recovered:
                    review = review.model_copy(update={
                        "coverage_gaps": list(dict.fromkeys(
                            review.coverage_gaps
                            + ["字段评审输出达到 token 上限；已保留完整字段，建议人工复核完整性"]
                        )),
                        "review_notes": (
                            review.review_notes + " reviewer JSON prefix recovered"
                        ).strip(),
                    })
                validated = self._validate_sources(
                    review,
                    valid_document_ids,
                    valid_paths,
                    valid_path_document_ids,
                )
                if not (validated.core_fields or validated.conditional_fields):
                    raise ValueError(
                        "all reviewer fields lacked compatible source evidence"
                    )
                return validated
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "sampling field review failed (attempt %d/%d) for %s: %s",
                    attempt,
                    self.maximum_attempts,
                    report_type,
                    exc,
                )
                prompt = (
                    system_prompt
                    + "\n\n上一次输出未通过 JSON Schema 或字段通用性校验："
                    + str(exc)[:500]
                    + "。请修正后重新输出；字段名不能含年份或 _E，且必须完整填写必需属性。"
                )
        raise ValueError(
            f"sampling field review failed after {self.maximum_attempts} attempts: {last_error}"
        ) from last_error

    @staticmethod
    def _validate_sources(
        review: CategoryFieldReview,
        valid_document_ids: set[str],
        valid_paths: set[str],
        valid_path_document_ids: dict[str, set[str]] | None = None,
    ) -> CategoryFieldReview:
        seen: set[str] = set()

        def clean(fields: list[GeneralFieldRecommendation], scope: str):
            cleaned: list[GeneralFieldRecommendation] = []
            for field in fields:
                source_ids = sorted(set(field.source_document_ids) & valid_document_ids)
                paths = list(dict.fromkeys(
                    path for path in field.observed_json_paths if path in valid_paths
                ))
                paths = _compatible_evidence_paths(field.field_name, paths)
                if valid_path_document_ids is not None:
                    # Source IDs and JSON paths are not independent evidence.
                    # Retain only documents that actually own at least one of
                    # the cited paths, preventing a model from inflating
                    # cross-document support by listing unrelated IDs.
                    source_ids = sorted({
                        document_id
                        for path in paths
                        for document_id in valid_path_document_ids.get(path, set())
                        if document_id in source_ids
                    })
                key = "".join(char.casefold() for char in field.field_name if char.isalnum())
                canonical_family = _canonical_field_family(
                    review.report_type, field.field_name
                )
                paths_have_business_evidence = any(
                    not _EXCLUDED_EVIDENCE_PATH_RE.search(path) for path in paths
                )
                if (
                    not source_ids
                    or not paths
                    or not paths_have_business_evidence
                    or not key
                    or key in seen
                    or _EXCLUDE_FIELD_RE.search(field.field_name)
                    # The model may cite an exact JSON path as the proposed
                    # field. Exact paths are evidence, not the reusable schema
                    # Atlas will send to every report in production.
                    or (
                        _RAW_JSON_FIELD_NAME_RE.search(field.field_name)
                        and canonical_family is None
                    )
                ):
                    continue
                seen.add(key)
                cleaned.append(field.model_copy(update={
                    "scope": scope,
                    "source_document_ids": source_ids,
                    "observed_json_paths": paths,
                    # Sampling discovers fields; model-authored example values
                    # are not trusted as evidence and remain available in the
                    # per-document free JSON instead.
                    "example_values": [],
                }))
            return cleaned

        validated_core = clean(review.core_fields, "CORE")
        validated_conditional = clean(review.conditional_fields, "CONDITIONAL")
        forced_conditional = [
            field for field in validated_core
            if (
                _FORCE_CONDITIONAL_RE.search(field.field_name)
                or len(field.source_document_ids) < 2
            )
        ]
        remaining_core = [
            field for field in validated_core
            if (
                not _FORCE_CONDITIONAL_RE.search(field.field_name)
                and len(field.source_document_ids) >= 2
            )
        ]
        # Derive sample cardinality from system-owned input, never from the
        # model-authored reviewed_document_count field.
        single_document_review = len(valid_document_ids) < 2
        if single_document_review:
            # A single document can suggest useful slots, but it cannot prove
            # cross-document or cross-subtype stability. Keep every proposal
            # provisional until a later sampling round supplies corroboration.
            forced_conditional = remaining_core + forced_conditional
            remaining_core = []
        core = remaining_core
        conditional = validated_conditional + [
            field.model_copy(update={"scope": "CONDITIONAL"})
            for field in forced_conditional
        ]
        core = _generalize_category_fields(
            review.report_type, core, valid_path_document_ids
        )
        conditional = _generalize_category_fields(
            review.report_type, conditional, valid_path_document_ids
        )
        # Canonical merging can narrow the actually cited evidence (for
        # example a macro metric label drops a non-macro profit path). Recheck
        # CORE after merging instead of keeping the model's earlier support
        # count.
        demoted_after_merge = [field for field in core if len(field.source_document_ids) < 2]
        core = [field for field in core if len(field.source_document_ids) >= 2]
        conditional = _generalize_category_fields(
            review.report_type,
            conditional + [
                field.model_copy(update={"scope": "CONDITIONAL"})
                for field in demoted_after_merge
            ],
            valid_path_document_ids,
        )
        if review.report_type == "macro":
            # Per-document JSON keeps detailed industrial splits and related
            # research. The reusable macro extraction profile should stay on
            # macro indicators, policy/events and risk transmission.
            macro_excluded = re.compile(r"行业划分|合作投资|合作与投资")
            core = [field for field in core if not macro_excluded.search(field.field_name)]
            conditional = [
                field for field in conditional
                if not macro_excluded.search(field.field_name)
            ]
            # Macro profiles describe indicators, policies/events and their
            # transmission. A single M&A report must not promote an incidental
            # "产业链竞争格局" path into the schema for every macro document.
            macro_allowed = re.compile(
                r"研究对象|宏观经济指标|宏观风险与约束|政策事件及影响|"
                r"关键风险与传导|宏观环境与风险"
            )
            core = [field for field in core if macro_allowed.search(field.field_name)]
            conditional = [
                field for field in conditional
                if macro_allowed.search(field.field_name)
            ]
        # Keep per-document JSON completely free-form, but prevent obvious
        # cross-type review noise from becoming a production profile. These
        # are type/field-level exclusions, not an allowlist, so genuinely new
        # reusable semantic families can still emerge from later samples.
        report_type_exclusions = {
            "industry": re.compile(r"^(?:估值|宏观指标|市场表现)$"),
            "strategy": re.compile(r"^行业重点新闻$"),
            "new_stock": re.compile(r"^市场表现与估值$"),
        }
        exclusion = report_type_exclusions.get(review.report_type)
        if exclusion is not None:
            core = [field for field in core if not exclusion.search(field.field_name)]
            conditional = [
                field for field in conditional
                if not exclusion.search(field.field_name)
            ]
        core_names = {field.field_name for field in core}
        conditional = [
            field for field in conditional if field.field_name not in core_names
        ]
        core = core[:8]
        conditional = conditional[:8]
        if len(core) + len(conditional) > 12:
            ranked = sorted(
                core + conditional,
                key=lambda field: (
                    0 if field.scope == "CORE" else 1,
                    field.priority,
                    field.field_name,
                ),
            )[:12]
            core = [field for field in ranked if field.scope == "CORE"]
            conditional = [field for field in ranked if field.scope == "CONDITIONAL"]

        rejected = []
        for item in review.rejected_over_specific_fields:
            source_ids = sorted(set(item.source_document_ids) & valid_document_ids)
            if source_ids:
                rejected.append(item.model_copy(update={"source_document_ids": source_ids}))

        coverage_gaps = list(review.coverage_gaps)
        if single_document_review:
            coverage_gaps.append(
                "当前类别只有一篇可读样本；全部字段暂列 CONDITIONAL，需扩样验证跨文档与跨子类型稳定性"
            )
        if review.report_type in {"stock", "industry"} and not any(
            re.search(r"产业链|上游|下游|供应|客户|产品|技术|应用", field.field_name)
            for field in core + conditional
        ):
            coverage_gaps.append(
                "当前样本没有可直接支撑的产业链上下游、产品技术或应用关系字段；需扩大样本"
            )

        return review.model_copy(update={
            "core_fields": core,
            "conditional_fields": conditional,
            "rejected_over_specific_fields": rejected,
            "coverage_gaps": list(dict.fromkeys(coverage_gaps)),
        })

    def _compact_document(self, result: FreeExtractionResult) -> dict[str, Any]:
        return {
            "document_id": result.document_id,
            "title": result.observed_title,
            "document_subtype": result.document_subtype,
            "quality_issues": result.quality_issues,
            "json_observations": _breadth_first_observations(
                result.content,
                maximum=self.maximum_observations_per_document,
            ),
        }

    @staticmethod
    def _compact_review(review: CategoryFieldReview) -> dict[str, Any]:
        def compact_field(field: GeneralFieldRecommendation) -> dict[str, Any]:
            return {
                "field_name": field.field_name,
                "description": field.description[:180],
                "scope": field.scope,
                "knowledge_graph_role": field.knowledge_graph_role,
                "value_shape": field.value_shape[:140],
                "applicability": field.applicability[:160],
                "source_document_ids": field.source_document_ids,
                "observed_json_paths": field.observed_json_paths[:4],
            }

        return {
            "core_fields": [compact_field(field) for field in review.core_fields[:10]],
            "conditional_fields": [
                compact_field(field) for field in review.conditional_fields[:10]
            ],
            "rejected_over_specific_fields": [
                item.model_dump(mode="json")
                for item in review.rejected_over_specific_fields[:8]
            ],
            "document_type_insights": review.document_type_insights[:8],
            "coverage_gaps": review.coverage_gaps[:8],
        }


def _breadth_first_observations(content: dict[str, Any], *, maximum: int) -> list[dict]:
    """Return a compact, business-first set of source observations.

    Free JSON often starts with tables, titles and analyst metadata. A plain
    breadth-first cutoff can therefore hide later ``核心内容`` or ``产业链``
    leaves from the reviewer. Traverse broadly, then rank leaves by KG value
    while retaining their exact paths for evidence validation.
    """
    candidates: list[tuple[int, dict[str, Any]]] = []
    queue: deque[tuple[str, Any]] = deque((str(key), value) for key, value in content.items())
    traversal_index = 0
    while queue and traversal_index < 640:
        path, value = queue.popleft()
        traversal_index += 1
        if isinstance(value, dict):
            if not value:
                candidates.append((traversal_index, {"path": path, "value": {}}))
            else:
                for key, child in value.items():
                    queue.append((f"{path}.{key}", child))
        elif isinstance(value, list):
            if not value:
                candidates.append((traversal_index, {"path": path, "value": []}))
            elif all(not isinstance(item, (dict, list)) for item in value):
                candidates.append((traversal_index, {"path": path, "value": value[:6]}))
            else:
                for index, child in enumerate(value[:4]):
                    queue.append((f"{path}[{index}]", child))
        else:
            text = str(value)
            candidates.append((traversal_index, {"path": path, "value": text[:240]}))

    ranked = sorted(
        candidates,
        key=lambda item: (-_observation_priority(item[1]["path"]), item[0]),
    )
    # Preserve semantic breadth. Large free JSON branches (often a table or a
    # single report section) must not consume the entire reviewer context and
    # hide products, customers, technology or supply-chain relations located
    # under sibling branches.
    selected: list[dict[str, Any]] = []
    selected_paths: set[str] = set()
    bucket_counts: dict[str, int] = {}
    per_bucket_limit = max(2, min(4, maximum // 4))
    for _, observation in ranked:
        bucket = _observation_bucket(observation["path"])
        if bucket_counts.get(bucket, 0) >= per_bucket_limit:
            continue
        selected.append(observation)
        selected_paths.add(observation["path"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        if len(selected) >= maximum:
            return selected
    for _, observation in ranked:
        if observation["path"] in selected_paths:
            continue
        selected.append(observation)
        if len(selected) >= maximum:
            break
    return selected


def _observation_bucket(path: str) -> str:
    parts = [part.split("[", 1)[0] for part in path.split(".")]
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return parts[0] if parts else path


def _path_document_index(
    results: list[FreeExtractionResult], *, maximum: int
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for result in results:
        for observation in _breadth_first_observations(result.content, maximum=maximum):
            index.setdefault(observation["path"], set()).add(result.document_id)
    return index


_HIGH_VALUE_PATH_RE = re.compile(
    r"研究对象|研究主题|核心|产业链|上游|下游|供应|客户|主营|业务|产品|技术|应用|"
    r"竞争|供需|需求|驱动|政策|事件|影响|风险|行业|市场|布局|合作|"
    r"company|business|product|service|industry_chain|upstream|downstream|supplier|customer|"
    r"technology|application|competit|capacity|demand|driver|policy|risk|market",
    re.I,
)
_LOW_VALUE_PATH_RE = re.compile(
    r"(^|\.)(?:title|document_id|report_type|sampling_subtype|发布日期|报告类型)$|"
    r"分析师|执业证书|联系方式|邮箱|电话|免责声明|法律声明|版权|chunk_page_ranges|"
    r"analyst|author|disclaimer|certificate|email|contact|publish_date",
    re.I,
)
_TABLE_PATH_RE = re.compile(r"(^|\.)(?:tables?|图表|表格|data)(?:\.|\[|$)", re.I)


def _observation_priority(path: str) -> int:
    if _LOW_VALUE_PATH_RE.search(path):
        return -100
    score = 0
    score += 30 * len(_HIGH_VALUE_PATH_RE.findall(path))
    if _TABLE_PATH_RE.search(path):
        score -= 20
    score -= min(path.count(".") + path.count("["), 8)
    return score


def _generalize_category_fields(
    report_type: str,
    fields: list[GeneralFieldRecommendation],
    path_document_ids: dict[str, set[str]] | None = None,
) -> list[GeneralFieldRecommendation]:
    """Merge model-proposed sibling metrics into reusable semantic slots."""
    buckets: dict[str, list[GeneralFieldRecommendation]] = {}
    passthrough: list[GeneralFieldRecommendation] = []
    for field in fields:
        canonical = _canonical_field_family(report_type, field.field_name)
        if canonical is None:
            passthrough.append(field)
        else:
            buckets.setdefault(canonical, []).append(field)

    merged = passthrough
    for canonical, members in buckets.items():
        base = min(members, key=lambda item: (item.priority, item.field_name))
        sources = sorted({
            source for member in members for source in member.source_document_ids
        })
        candidate_paths = list(dict.fromkeys(
            path for member in members for path in member.observed_json_paths
        ))
        candidate_paths = _compatible_evidence_paths(canonical, candidate_paths)
        paths = _select_covering_paths(
            candidate_paths,
            sources,
            path_document_ids,
            maximum=3,
        )
        if path_document_ids is not None:
            sources = sorted({
                document_id
                for path in paths
                for document_id in path_document_ids.get(path, set())
                if document_id in sources
            })
        details = _CANONICAL_FIELD_DETAILS[canonical]
        merged.append(base.model_copy(update={
            "field_name": canonical,
            "description": details[0],
            "knowledge_graph_role": details[1],
            "value_shape": details[2],
            "applicability": details[3],
            "source_document_ids": sources,
            "observed_json_paths": paths,
            "example_values": [],
        }))
    return sorted(merged, key=lambda item: (item.priority, item.field_name))


def _select_covering_paths(
    paths: list[str],
    source_document_ids: list[str],
    path_document_ids: dict[str, set[str]] | None,
    *,
    maximum: int,
) -> list[str]:
    if path_document_ids is None:
        return paths[:maximum]
    remaining = set(source_document_ids)
    selected: list[str] = []
    candidates = list(paths)
    while candidates and len(selected) < maximum:
        path = max(
            candidates,
            key=lambda item: (
                len(path_document_ids.get(item, set()) & remaining),
                len(path_document_ids.get(item, set())),
                -paths.index(item),
            ),
        )
        selected.append(path)
        remaining -= path_document_ids.get(path, set())
        candidates.remove(path)
    return selected


_CANONICAL_FIELD_DETAILS: dict[str, tuple[str, str, str, str]] = {
    "研究对象": (
        "报告所研究的公司、行业、资产、地区或宏观主题",
        "RESEARCH_REPORT_STUDIES_ENTITY",
        "{entity_name,entity_type,security_code,industry}",
        "报告明确给出研究主体时",
    ),
    "宏观经济指标": (
        "可跨宏观子主题承载的指标、期间、值、单位与变化方向",
        "MACRO_INDICATOR",
        "[{metric_name,period,value,unit,change,region}]",
        "macro 报告披露财政、货币、增长、通胀、就业或地产指标时",
    ),
    "宏观风险与约束": (
        "宏观运行中的主要压力、风险对象及传导方向",
        "RISK_TRANSMISSION",
        "[{risk,affected_entity,mechanism,direction}]",
        "macro 报告讨论风险或约束时",
    ),
    "政策事件及影响": (
        "政策或制度事件、作用对象、传导机制与预期影响",
        "POLICY_AFFECTS_ENTITY",
        "[{policy_or_event,target,mechanism,impact,direction}]",
        "报告包含政策、监管或重大制度事件时",
    ),
    "业务板块与主营产品/服务": (
        "公司的业务板块、主营产品或服务及其结构",
        "COMPANY_PRODUCES_PRODUCT_OR_SERVICE",
        "[{segment,products_or_services,revenue_share}]",
        "公司研报披露业务构成或主要供给时",
    ),
    "产业链定位": (
        "研究对象所处产业链环节、承担的功能及其上下游边界",
        "ENTITY_PARTICIPATES_IN_INDUSTRY_CHAIN",
        "[{entity,chain,stage,role}]",
        "公司或行业报告明确描述产业链环节时",
    ),
    "上游投入与供应关系": (
        "核心原材料、设备、技术投入及供应主体之间的关系",
        "SUPPLIER_OR_INPUT_SUPPORTS_ENTITY",
        "[{input,supplier,target,relationship,dependency}]",
        "报告披露上游投入、采购或供应商时",
    ),
    "下游应用与客户关系": (
        "产品或服务面向的应用场景、客户类型和关键客户关系",
        "ENTITY_PRODUCT_SERVES_APPLICATION_OR_CUSTOMER",
        "[{product_or_service,application,customer,relationship}]",
        "报告披露应用、客户或销售去向时",
    ),
    "核心技术与技术路线": (
        "研究对象的核心技术、工艺能力、研发壁垒与技术演进路线",
        "ENTITY_USES_OR_DEVELOPS_TECHNOLOGY",
        "[{entity,technology,capability,barrier,route}]",
        "报告披露技术、研发、专利、工艺或路线时",
    ),
    "竞争格局与竞争关系": (
        "行业或公司的主要竞争者、市场结构、竞争优势与替代关系",
        "ENTITY_COMPETES_WITH_ENTITY",
        "[{subject,competitor,market,position,advantage}]",
        "报告披露竞争者、份额或竞争壁垒时",
    ),
    "产能与项目布局": (
        "产能、生产基地、在建或募投项目及投产进度",
        "ENTITY_HAS_CAPACITY_OR_PROJECT",
        "[{entity,project_or_base,capacity,unit,status,timeline,location}]",
        "报告披露产能、基地或项目建设时",
    ),
    "关键风险与传导": (
        "关键风险、影响对象、传导机制与潜在后果",
        "RISK_AFFECTS_ENTITY",
        "[{risk,affected_entity,mechanism,consequence}]",
        "报告披露经营、行业、政策或市场风险时",
    ),
    "市场表现与市场信号": (
        "市场、行业或资产的表现，以及资金、情绪和技术信号",
        "MARKET_SIGNAL",
        "[{subject,period,signal_type,value,direction}]",
        "晨会或策略报告包含市场回顾、行业表现、资金或技术信号时",
    ),
    "宏观环境与风险": (
        "宏观环境、主要挑战、风险对象与潜在传导方向",
        "MACRO_ENVIRONMENT_AFFECTS_ENTITY",
        "[{factor,affected_entity,direction,mechanism}]",
        "晨会或策略报告讨论宏观环境与风险时",
    ),
    "投资建议/评级": (
        "对行业、公司、资产或配置方向的建议与评级",
        "ANALYST_RECOMMENDS_ENTITY_OR_DIRECTION",
        "[{subject,recommendation,rating,horizon,rationale}]",
        "报告明确给出投资建议、评级或关注方向时",
    ),
    "行业状态与驱动": (
        "行业景气、趋势、情绪及其关键供需或经营驱动因素",
        "FACTOR_AFFECTS_INDUSTRY",
        "[{industry,period,status,direction,driver,impact}]",
        "industry 报告讨论行业趋势、景气或业绩驱动时",
    ),
    "公司经营表现": (
        "公司经营结果、变化方向、原因及其相对行业表现",
        "COMPANY_HAS_OPERATING_PERFORMANCE",
        "[{company,period,metric,value,unit,change,driver,industry_comparison}]",
        "stock 报告讨论公司经营或业绩表现时",
    ),
    "供需格局与驱动": (
        "行业或公司面对的供给、需求、库存、产能、周期与增长驱动",
        "SUPPLY_DEMAND_FACTOR_AFFECTS_ENTITY",
        "[{factor_type,factor,subject,direction,mechanism,period}]",
        "stock 或 industry 报告讨论供需、周期或增长驱动时",
    ),
    "财务与盈利预测": (
        "历史或预测财务指标的期间、口径、数值、单位与假设",
        "ENTITY_HAS_FINANCIAL_METRIC_OR_FORECAST",
        "[{entity,metric,period,value,unit,is_forecast,assumption}]",
        "公司、行业或策略报告披露财务数据或预测时",
    ),
}


def _canonical_field_family(report_type: str, field_name: str) -> str | None:
    if re.search(r"研究对象|研究主题|公司名称|company_name|company_profile|company_overview", field_name, re.I):
        return "研究对象"
    if report_type == "morning_report" and re.search(
        r"宏观经济环境|国内经济挑战|宏观环境|经济挑战", field_name
    ):
        return "宏观环境与风险"
    if re.search(r"投资建议|投资评级|推荐标的|行业投资建议", field_name):
        return "投资建议/评级"
    if re.search(r"政策背景|政策影响|政策事件|事件影响", field_name):
        return "政策事件及影响"
    if re.search(r"关键风险|风险提示|风险因素|风险传导|风险$", field_name):
        return "关键风险与传导"
    if report_type == "macro":
        if re.search(r"政策意图|政策期望|操作机制", field_name):
            return "政策事件及影响"
        if re.search(r"风险|压力|约束", field_name):
            return "宏观风险与约束"
        if re.search(
            r"财政|税收|地方债|地方政府债|货币|通胀|就业|房地产|PMI|GDP|进出口|"
            r"汇率|利率|工业企业利润|行业利润|利润变化趋势|经济指标|经济数据|"
            r"宏观指标|关键经营指标",
            field_name,
            re.I,
        ):
            return "宏观经济指标"
    if report_type == "industry":
        if re.search(r"industry_overview\.(?:status|sentiment)|行业(?:状态|趋势|情绪|景气)", field_name, re.I):
            return "行业状态与驱动"
        if re.search(r"industry_challenges\.(?:factors|impact)|行业(?:挑战|驱动|影响因素)", field_name, re.I):
            return "关键风险与传导"
    if report_type == "morning_report":
        if re.search(r"货币政策|重点支持领域|资本市场改革|政策", field_name):
            return "政策事件及影响"
        if re.search(
            r"市场表现|行业表现|市场平衡|市场技术指标|海外市场指数|市场涨跌幅|"
            r"市场指数表现|市场供需状况|市场热点概念|市场技术分析|市场预期|"
            r"行情|资金|情绪",
            field_name,
        ):
            return "市场表现与市场信号"
        if re.search(r"宏观经济环境|国内经济挑战|宏观环境|经济挑战", field_name):
            return "宏观环境与风险"
    if report_type in {"stock", "new_stock", "morning_report"}:
        # Evaluate technology before generic product/business terms so a path
        # such as products_and_technology becomes a technology relationship,
        # not merely a business-segment field.
        if re.search(
            r"核心技术|技术路线|技术壁垒|技术进展|产品分类与技术特点|"
            r"研发|technology|technical|r_and_d",
            field_name,
            re.I,
        ):
            return "核心技术与技术路线"
        if re.search(
            r"主营产品|主要产品或服务|主营业务|业务板块|业务结构|业务构成|"
            r"main_business|core_business|"
            r"products?_and_services?",
            field_name,
            re.I,
        ):
            return "业务板块与主营产品/服务"
    if report_type in {"stock", "new_stock"} and re.search(
        r"公司业绩表现|经营表现|业绩表现|performance|analysis_logic\.theme",
        field_name,
        re.I,
    ):
        return "公司经营表现"
    if report_type in {"stock", "industry", "new_stock", "strategy", "morning_report"} and re.search(
        r"长期驱动因素|需求驱动|供给驱动|主要驱动因素|供需驱动|行业周期性|行业订单|"
        r"市场预测|市场规模预测|增长预测|"
        r"industry_cyclicality|market_drivers?|driver$",
        field_name,
        re.I,
    ):
        return "供需格局与驱动"
    if report_type in {"stock", "industry", "new_stock", "morning_report"}:
        if re.search(r"产业链定位|产业链位置|所处环节|industry_chain", field_name, re.I):
            return "产业链定位"
        if re.search(r"上游|供应商|供应关系|原材料|upstream|supplier", field_name, re.I):
            return "上游投入与供应关系"
        if re.search(r"下游|客户|应用(?:场景|领域)|客户关系|downstream|customer|application", field_name, re.I):
            return "下游应用与客户关系"
        if re.search(r"核心技术|技术路线|技术壁垒|研发|technology|technical|r_and_d", field_name, re.I):
            return "核心技术与技术路线"
        if re.search(r"竞争格局|竞争关系|竞争对手|竞争优势|competit", field_name, re.I):
            return "竞争格局与竞争关系"
        if re.search(r"产能|项目布局|生产基地|募投项目|capacity|production_base", field_name, re.I):
            return "产能与项目布局"
    if report_type in {"strategy", "morning_report"} and re.search(
        r"市场趋势|行业资金流动|资金流|市场表现|市场信号|market_(?:trend|signal)|fund_flow",
        field_name,
        re.I,
    ):
        return "市场表现与市场信号"
    if re.search(r"财务预测|盈利预测|估值预测|financial_forecast|financials|forecast", field_name, re.I):
        return "财务与盈利预测"
    return None


def _cited_source_observations(
    reviews: list[CategoryFieldReview],
    compact_documents: dict[str, dict[str, Any]],
    *,
    maximum: int,
) -> list[dict[str, Any]]:
    cited_paths = {
        path
        for review in reviews
        for field in review.core_fields + review.conditional_fields
        for path in field.observed_json_paths
    }
    result: list[dict[str, Any]] = []
    for document_id, document in compact_documents.items():
        for observation in document["json_observations"]:
            if observation["path"] in cited_paths:
                result.append({
                    "document_id": document_id,
                    "path": observation["path"],
                    "value": observation["value"],
                })
                if len(result) >= maximum:
                    return result
    return result


def _compatible_evidence_paths(field_name: str, paths: list[str]) -> list[str]:
    for field_pattern, evidence_pattern in _FIELD_EVIDENCE_RULES:
        if field_pattern.search(field_name):
            paths = [path for path in paths if evidence_pattern.search(path)]
            break
    for field_pattern, excluded_pattern in _FIELD_EVIDENCE_EXCLUSIONS:
        if field_pattern.search(field_name):
            paths = [path for path in paths if not excluded_pattern.search(path)]
    return paths


def _parse_review_response(raw: str) -> tuple[CategoryFieldReview, bool]:
    last_error: Exception | None = None
    for value, recovered in _review_json_candidates(raw):
        try:
            for key in ("core_fields", "conditional_fields"):
                for field in value.get(key) or []:
                    if isinstance(field, dict):
                        field["example_values"] = list(field.get("example_values") or [])[:2]
                        field["observed_json_paths"] = list(
                            field.get("observed_json_paths") or []
                        )[:3]
            review = CategoryFieldReview.model_validate(value)
            if not (review.core_fields or review.conditional_fields):
                raise ValueError("field reviewer returned no reusable fields")
            return review, recovered
        except Exception as exc:
            last_error = exc
    detail = f": {last_error}" if last_error is not None else ""
    raise ValueError(f"field reviewer returned invalid or incomplete JSON{detail}")


def _review_json_candidates(raw: str):
    """Yield the full review, then progressively earlier complete JSON prefixes."""
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            yield value, False
            return
    except Exception:
        pass

    start = raw.find("{")
    if start == -1:
        return
    stack: list[str] = []
    commas: list[tuple[int, tuple[str, ...]]] = []
    in_string = False
    escaped = False
    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if stack:
                stack.pop()
            if not stack:
                try:
                    value = json.loads(raw[start : index + 1])
                    if isinstance(value, dict):
                        yield value, False
                except Exception:
                    pass
                return
        elif char == "," and stack:
            commas.append((index, tuple(stack)))

    for end, open_containers in reversed(commas):
        closers = "".join(
            "}" if char == "{" else "]" for char in reversed(open_containers)
        )
        try:
            value = json.loads(raw[start:end].rstrip() + closers)
        except Exception:
            continue
        if isinstance(value, dict):
            yield value, True

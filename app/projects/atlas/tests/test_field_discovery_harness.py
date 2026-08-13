import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from atlas.knowledge_production.extractor.free_extractor import (
    FreeExtractionExtractor,
    _parse_free_content,
)
from atlas.knowledge_production.ontology_discovery.free_field_reviewer import (
    FreeFieldReviewSummariser,
    _breadth_first_observations,
    _parse_review_response,
)
from atlas.knowledge_production.pdf_preprocessor import (
    PDFTextPage,
    RapidOCRLayoutParser,
    assess_pdf_text_quality,
    chunk_pdf_pages,
)
from atlas.knowledge_production.pdf_preprocessor.layout_sidecar import (
    _representative_page_indexes,
)
from atlas.application.free_extraction_runner import FreeExtractionRunner
from atlas.models import ExtractionRun, ExtractionRunStatus, ResearchReport
from atlas.models.free_extraction import (
    CategoryFieldReview,
    FreeExtractionResult,
    GeneralFieldRecommendation,
)


def test_page_chunking_preserves_boundaries_and_reports_budget_sampling():
    pages = [PDFTextPage(index, "正文" * 400) for index in range(1, 8)]
    chunks = chunk_pdf_pages(pages, maximum_chunk_tokens=600, maximum_chunks=3)
    assert len(chunks) == 3
    assert chunks[0].page_numbers == [1]
    assert chunks[-1].page_numbers == [7]
    assert all(chunk.coverage_truncated for chunk in chunks)


def test_page_chunking_prefers_research_content_over_disclaimer_tail():
    pages = [
        PDFTextPage(1, "核心观点 产品 技术 下游市场" * 80),
        PDFTextPage(2, "行业供需与竞争格局" * 120),
        PDFTextPage(3, "客户与供应商关系" * 120),
        PDFTextPage(4, "免责声明 本报告仅供 版权所有 未经书面许可 " * 100),
    ]
    chunks = chunk_pdf_pages(pages, maximum_chunk_tokens=500, maximum_chunks=2)
    assert chunks[0].page_numbers == [1]
    assert chunks[1].page_numbers != [4]


def test_text_quality_does_not_escalate_chart_labels_when_narrative_is_useful():
    pages = [
        PDFTextPage(1, "12% 8% 4% 0% -4% -8% -12% 公司拟启动医药物流仓储资产项目，收入增长并提示风险" * 8),
        PDFTextPage(2, "公司产品、客户、产业链布局与核心观点" * 20),
    ]
    quality = assess_pdf_text_quality(pages)
    assert not quality.requires_layout_fallback


def test_text_quality_routes_scanned_pdf_to_ocr_sidecar():
    quality = assess_pdf_text_quality([
        PDFTextPage(1, ""),
        PDFTextPage(2, "页码 2"),
        PDFTextPage(3, ""),
        PDFTextPage(4, ""),
        PDFTextPage(5, ""),
    ])
    assert quality.requires_layout_fallback
    assert quality.recommended_parser == "pp-structure-v3-ocr"


def test_local_ocr_selects_bounded_representative_pages():
    assert _representative_page_indexes(100, 1) == [0]
    assert _representative_page_indexes(0, 5) == []
    assert _representative_page_indexes(3, 12) == [0, 1, 2]
    indexes = _representative_page_indexes(100, 5)
    assert indexes == [0, 25, 50, 74, 99]


@pytest.mark.asyncio
async def test_local_ocr_serializes_worker_calls(monkeypatch):
    parser = RapidOCRLayoutParser()
    calls = []

    def fake_extract(pdf):
        calls.append(pdf)
        return [PDFTextPage(1, "正文")]

    monkeypatch.setattr(parser, "_extract_sync", fake_extract)
    first, second = await __import__("asyncio").gather(
        parser.extract_pages(b"a", filename="a.pdf"),
        parser.extract_pages(b"b", filename="b.pdf"),
    )
    assert calls == [b"a", b"b"]
    assert first[0].text == "正文" and second[0].text == "正文"


@pytest.mark.asyncio
async def test_free_runner_reuses_same_prompt_result_without_reading_pdf():
    report = ResearchReport(
        source="eastmoney",
        resource_id="r1",
        report_type="stock",
        publish_date="2026-01-01",
        title="公司深度",
        org_name="Test Broker",
        pdf_object_key="r1.pdf",
        status="downloaded",
    )
    stored_run = ExtractionRun(
        source_document_id=report.document_id,
        source_report_type="stock",
        pipeline_version="pipeline-v1",
        model_id="fake",
        prompt_signature="same-signature",
        extraction_schema_version="free-document-understanding-v8",
        semantic_version="free-discovery",
        status=ExtractionRunStatus.SUCCEEDED,
    )

    class Store:
        async def find_reusable_extraction(self, *args):
            assert args == (
                report.document_id,
                "free-discovery",
                "pipeline-v1",
                "same-signature",
            )
            return stored_run, FreeExtractionResult(
                document_id=report.document_id,
                report_type="stock",
                content={"公司": {"主营产品": ["交换机芯片"]}},
            ).model_dump(mode="json")

        async def create_extraction_run(self, _):
            raise AssertionError("cache hit must not create a new extraction run")

    class Reader:
        def read(self, _):
            raise AssertionError("cache hit must not read the PDF")

    extractor = SimpleNamespace(
        llm=SimpleNamespace(model_id="fake"),
        prompt_builder=SimpleNamespace(
            signature=lambda _profile, _model: "same-signature"
        ),
    )
    outcome = await FreeExtractionRunner(
        reader=Reader(),
        store=Store(),
        extractor=extractor,
        unlocker=SimpleNamespace(),
        pipeline_version="pipeline-v1",
    ).run_document(report, report_profile={})
    assert outcome.run.id == stored_run.id
    assert outcome.result.content["公司"]["主营产品"] == ["交换机芯片"]


def test_free_content_parser_accepts_document_json_and_rejects_status_envelope():
    content = _parse_free_content('{"业务结构":{"产品":["交换机芯片"]}}')
    assert content["业务结构"]["产品"] == ["交换机芯片"]
    with pytest.raises(ValueError, match="status envelope"):
        _parse_free_content('{"status":"success","message":"任务完成"}')


def test_free_content_parser_recovers_only_complete_values_from_truncated_json():
    content = _parse_free_content(
        '{"产业链":{"上游":["晶圆代工"],"下游":["数据中心"]},'
        '"产品技术":{"系列":["TsingMa"],"说明":"未完成'
    )
    assert content == {
        "产业链": {"上游": ["晶圆代工"], "下游": ["数据中心"]},
        "产品技术": {"系列": ["TsingMa"]},
    }


@pytest.mark.asyncio
async def test_single_chunk_keeps_model_authored_json_without_candidate_schema(monkeypatch):
    class LLM:
        model_id = "fake"
        input_mode = "TEXT_EXTRACTED"
        config = SimpleNamespace(context_window_tokens=8192)

        async def complete_text(self, **kwargs):
            assert kwargs["response_schema"] is None
            return json.dumps({
                "公司与定位": {"公司": "盛科通信", "定位": "交换机芯片厂商"},
                "产业链": {"下游应用": ["数据中心", "企业网络"]},
            }, ensure_ascii=False)

    monkeypatch.setattr(
        "atlas.knowledge_production.extractor.free_extractor.extract_pdf_pages",
        lambda _: [PDFTextPage(1, "盛科通信是交换机芯片厂商，下游用于数据中心")],
    )
    extractor = FreeExtractionExtractor(LLM(), maximum_total_attempts=1)
    result, attempts = await extractor.extract(
        pdf=b"pdf",
        filename="a.pdf",
        document_id="d1",
        title="公司深度",
        report_type="stock",
        report_profile={"sampling_subtype": "公司深度"},
    )
    assert attempts == 1
    assert result.readable
    assert result.content["产业链"]["下游应用"] == ["数据中心", "企业网络"]
    assert "candidate_fields" not in result.content


@pytest.mark.asyncio
async def test_layout_sidecar_is_called_only_when_quality_gate_requests_it(monkeypatch):
    class LLM:
        model_id = "fake"
        input_mode = "TEXT_EXTRACTED"
        config = SimpleNamespace(context_window_tokens=8192)

        async def complete_text(self, **kwargs):
            assert "产业链" in kwargs["extracted_text"]
            return '{"产业链":{"上游":"晶圆代工","下游":"数据中心"}}'

    class Sidecar:
        def __init__(self):
            self.calls = 0

        async def extract_pages(self, pdf, *, filename):
            self.calls += 1
            return [PDFTextPage(1, "产业链上游晶圆代工，下游应用为数据中心" * 20)]

    monkeypatch.setattr(
        "atlas.knowledge_production.extractor.free_extractor.extract_pdf_pages",
        lambda _: [PDFTextPage(1, "")],
    )
    sidecar = Sidecar()
    result, _ = await FreeExtractionExtractor(
        LLM(), maximum_total_attempts=1, layout_sidecar=sidecar
    ).extract(
        pdf=b"pdf", filename="scan.pdf", document_id="d1", title="扫描报告", report_type="stock"
    )
    assert result.readable
    assert sidecar.calls == 1
    assert "LAYOUT_SIDECAR_USED" in result.quality_issues


@pytest.mark.asyncio
async def test_layout_sidecar_is_skipped_for_good_text_layer(monkeypatch):
    class LLM:
        model_id = "fake"
        input_mode = "TEXT_EXTRACTED"
        config = SimpleNamespace(context_window_tokens=8192)

        async def complete_text(self, **kwargs):
            return '{"主营产品":["交换机芯片"]}'

    class Sidecar:
        async def extract_pages(self, *_args, **_kwargs):
            raise AssertionError("good text must not call sidecar")

    monkeypatch.setattr(
        "atlas.knowledge_production.extractor.free_extractor.extract_pdf_pages",
        lambda _: [PDFTextPage(1, "公司主营交换机芯片，产品用于数据中心，产业链客户需求增长" * 20)],
    )
    result, _ = await FreeExtractionExtractor(
        LLM(), maximum_total_attempts=1, layout_sidecar=Sidecar()
    ).extract(
        pdf=b"pdf", filename="text.pdf", document_id="d1", title="文本报告", report_type="stock"
    )
    assert result.readable
    assert "LAYOUT_SIDECAR_USED" not in result.quality_issues


@pytest.mark.asyncio
async def test_model_declared_unreadable_chunk_is_not_retried(monkeypatch):
    class LLM:
        model_id = "fake"
        input_mode = "TEXT_EXTRACTED"
        config = SimpleNamespace(context_window_tokens=8192)

        def __init__(self):
            self.calls = 0

        async def complete_text(self, **kwargs):
            self.calls += 1
            return '{"readability":"UNREADABLE","readability_reason":"只有免责声明"}'

    monkeypatch.setattr(
        "atlas.knowledge_production.extractor.free_extractor.extract_pdf_pages",
        lambda _: [PDFTextPage(1, "免责声明")],
    )
    llm = LLM()
    result, attempts = await FreeExtractionExtractor(
        llm, maximum_total_attempts=2
    ).extract(
        pdf=b"pdf",
        filename="a.pdf",
        document_id="d1",
        title="空白页",
        report_type="stock",
    )
    assert not result.readable
    assert attempts == 1
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_multi_chunk_map_results_are_merged_into_one_readable_json(monkeypatch):
    class LLM:
        model_id = "fake"
        input_mode = "TEXT_EXTRACTED"
        config = SimpleNamespace(context_window_tokens=3000)

        def __init__(self):
            self.calls = 0

        async def complete_text(self, **kwargs):
            self.calls += 1
            if kwargs["filename"].endswith("chunk-results.json"):
                return '{"产业链":{"上游":["晶圆代工"],"下游":["数据中心"]},"风险":["竞争加剧"]}'
            return (
                '{"上游":["晶圆代工"]}'
                if self.calls == 1
                else '{"下游":["数据中心"],"风险":["竞争加剧"]}'
            )

    pages = [PDFTextPage(1, "上游晶圆代工" * 300), PDFTextPage(2, "下游数据中心" * 300)]
    monkeypatch.setattr(
        "atlas.knowledge_production.extractor.free_extractor.extract_pdf_pages",
        lambda _: pages,
    )
    llm = LLM()
    extractor = FreeExtractionExtractor(
        llm,
        maximum_total_attempts=1,
        chunk_output_tokens=512,
        merge_output_tokens=800,
        maximum_chunks=2,
        prompt_reserve_tokens=512,
    )
    result, attempts = await extractor.extract(
        pdf=b"pdf",
        filename="a.pdf",
        document_id="d1",
        title="公司深度",
        report_type="stock",
    )
    assert attempts == 3
    assert llm.calls == 3
    assert result.content["产业链"]["上游"] == ["晶圆代工"]
    assert result.content["风险"] == ["竞争加剧"]


def test_review_field_rejects_concrete_year_and_e_suffix():
    base = {
        "description": "预测指标",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "metric",
        "value_shape": "{period,value,unit}",
        "applicability": "业绩预测",
        "rationale": "可复用",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    with pytest.raises(ValidationError):
        GeneralFieldRecommendation(field_name="2025净利润", **base)
    with pytest.raises(ValidationError):
        GeneralFieldRecommendation(field_name="每股收益_E", **base)


def test_field_review_recovers_complete_fields_from_truncated_output():
    field = {
        "field_name": "主营产品与服务",
        "description": "主要供给",
        "scope": "CORE",
        "knowledge_graph_role": "COMPANY-PRODUCES-PRODUCT",
        "value_shape": "[{name}]",
        "applicability": "公司研报",
        "rationale": "产业链供给端",
        "priority": 1,
        "source_document_ids": ["d1"],
        "observed_json_paths": ["公司.产品"],
        "example_values": ["交换机芯片"],
    }
    raw = json.dumps({
        "report_type": "stock",
        "reviewed_document_count": 2,
        "core_fields": [field, {**field, "field_name": "未完成字段"}],
        "conditional_fields": [],
    }, ensure_ascii=False)
    truncated = raw[: raw.index('"field_name": "未完成字段"') + 12]
    review, recovered = _parse_review_response(truncated)
    assert recovered
    assert [item.field_name for item in review.core_fields] == ["主营产品与服务"]


def test_field_reviewer_forces_optional_metrics_out_of_core_scope():
    review = CategoryFieldReview.model_validate({
        "report_type": "industry",
        "core_fields": [{
            "field_name": "关键经营指标",
            "description": "行业特有指标集合",
            "scope": "CORE",
            "knowledge_graph_role": "量化指标",
            "value_shape": "[{metric_name,period,value,unit}]",
            "applicability": "披露经营指标时",
            "rationale": "统一容纳行业指标",
            "priority": 3,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["经营.污泥处理量"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"经营.污泥处理量"}
    )
    assert cleaned.core_fields == []
    assert [item.field_name for item in cleaned.conditional_fields] == ["关键经营指标"]


def test_single_document_review_keeps_all_proposals_provisional():
    review = CategoryFieldReview.model_validate({
        "report_type": "stock",
        "reviewed_document_count": 1,
        "core_fields": [{
            "field_name": "主营产品与服务",
            "description": "公司主要供给",
            "scope": "CORE",
            "knowledge_graph_role": "PRODUCES",
            "value_shape": "array",
            "applicability": "公司研报",
            "rationale": "样本文档出现",
            "priority": 1,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["业务.主营产品"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"业务.主营产品"}
    )
    assert cleaned.core_fields == []
    assert [item.field_name for item in cleaned.conditional_fields] == [
        "业务板块与主营产品/服务"
    ]
    assert any("一篇可读样本" in gap for gap in cleaned.coverage_gaps)


def test_raw_json_path_is_not_published_as_a_reusable_field_name():
    review = CategoryFieldReview.model_validate({
        "report_type": "stock",
        "conditional_fields": [{
            "field_name": "financial_forecasts.unit",
            "description": "raw path fragment",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "metric unit",
            "value_shape": "string",
            "applicability": "stock reports",
            "rationale": "observed once",
            "priority": 3,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["financial_forecasts.unit"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"financial_forecasts.unit"}
    )
    assert cleaned.core_fields == []
    assert [field.field_name for field in cleaned.conditional_fields] == [
        "财务与盈利预测"
    ]


def test_english_new_stock_paths_are_generalized_into_kg_semantic_families():
    common = {
        "description": "observed business semantics",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "relationship",
        "value_shape": "object",
        "applicability": "new stock reports",
        "rationale": "source JSON contains it",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "new_stock",
        "conditional_fields": [
            {**common, "field_name": "products_and_technology", "observed_json_paths": ["products_and_technology.core_technology"]},
            {**common, "field_name": "customers_and_competition", "observed_json_paths": ["customers_and_competition.key_customers"]},
            {**common, "field_name": "company_profile", "observed_json_paths": ["company_profile.main_business"]},
        ],
    })
    paths = {field.observed_json_paths[0] for field in review.conditional_fields}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert {field.field_name for field in cleaned.conditional_fields} == {
        "核心技术与技术路线",
        "下游应用与客户关系",
        "研究对象",
    }


def test_observation_compaction_prefers_business_semantics_over_tables_and_metadata():
    content = {
        "tables": {
            "图表1": {"data": {f"指标{index}": index for index in range(40)}}
        },
        "分析师": {"姓名": "某分析师", "电话": "123"},
        "核心内容": {
            "研究对象": "北交所上市公司",
            "政策影响": "服务专精特新企业的定位强化",
            "风险因素": ["监管政策收紧"],
        },
    }
    observations = _breadth_first_observations(content, maximum=3)
    paths = {item["path"] for item in observations}
    assert "核心内容.研究对象" in paths
    assert "核心内容.政策影响" in paths
    assert all("分析师" not in path for path in paths)


def test_observation_compaction_preserves_sibling_business_sections():
    content = {
        "核心内容": {
            "风险": {f"风险{index}": "不及预期" for index in range(30)},
            "主营产品": {"产品": "交换机芯片"},
            "下游应用": {"场景": "数据中心"},
            "核心技术": {"能力": "高速转发"},
        },
        "供需格局": {"需求驱动": "AI 算力建设"},
    }
    observations = _breadth_first_observations(content, maximum=8)
    paths = {item["path"] for item in observations}
    assert any("主营产品" in path for path in paths)
    assert any("下游应用" in path for path in paths)
    assert any("核心技术" in path for path in paths)
    assert any("供需格局" in path for path in paths)


def test_macro_single_document_metrics_merge_into_one_conditional_slot():
    common = {
        "description": "财政数据",
        "scope": "CORE",
        "knowledge_graph_role": "macro",
        "value_shape": "object",
        "applicability": "财政报告",
        "rationale": "输入出现",
        "priority": 1,
        "source_document_ids": ["d1", "d2"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "macro",
        "reviewed_document_count": 1,
        "core_fields": [
            {
                **common,
                "field_name": "财政支出总额及同比变化",
                "observed_json_paths": ["核心观点.一般公共预算支出.金额"],
            },
            {
                **common,
                "field_name": "财政收入完成进度",
                "observed_json_paths": ["核心观点.一般公共预算收入.完成进度"],
            },
        ],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review,
        {"d1"},
        {"核心观点.一般公共预算支出.金额", "核心观点.一般公共预算收入.完成进度"},
    )
    assert cleaned.core_fields == []
    assert [item.field_name for item in cleaned.conditional_fields] == ["宏观经济指标"]
    assert len(cleaned.conditional_fields[0].observed_json_paths) == 2


def test_macro_operating_label_and_metadata_do_not_fragment_profile():
    common = {
        "description": "宏观字段",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "macro",
        "value_shape": "object",
        "applicability": "宏观报告",
        "rationale": "输入出现",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "macro",
        "conditional_fields": [
            {
                **common,
                "field_name": "关键经营指标",
                "observed_json_paths": ["核心观点.一般公共预算支出.金额"],
            },
            {
                **common,
                "field_name": "合作投资",
                "observed_json_paths": ["相关研究"],
            },
            {
                **common,
                "field_name": "行业划分",
                "observed_json_paths": ["行业划分.上游"],
            },
        ],
    })
    paths = {item.observed_json_paths[0] for item in review.conditional_fields}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert [item.field_name for item in cleaned.conditional_fields] == ["宏观经济指标"]


def test_macro_industrial_profit_path_supports_macro_indicator():
    review = CategoryFieldReview.model_validate({
        "report_type": "macro",
        "conditional_fields": [{
            "field_name": "宏观指标",
            "description": "工业企业利润指标",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "MACRO_INDICATOR",
            "value_shape": "array",
            "applicability": "宏观报告",
            "rationale": "输入出现",
            "priority": 1,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["行业分析.工业企业.企业利润降幅"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"行业分析.工业企业.企业利润降幅"}
    )
    assert [item.field_name for item in cleaned.conditional_fields] == ["宏观经济指标"]


def test_macro_profile_drops_incidental_industry_competition_field():
    common = {
        "description": "policy effect",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "relation",
        "value_shape": "object",
        "applicability": "macro reports",
        "rationale": "observed",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "macro",
        "conditional_fields": [
            {**common, "field_name": "政策事件及影响", "observed_json_paths": ["政策.政策影响"]},
            {**common, "field_name": "产业链竞争格局", "observed_json_paths": ["政策.产业链影响.科技企业"]},
        ],
    })
    paths = {field.observed_json_paths[0] for field in review.conditional_fields}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert [field.field_name for field in cleaned.conditional_fields] == [
        "政策事件及影响"
    ]


def test_strategy_fund_flow_is_generalized_to_market_signal():
    review = CategoryFieldReview.model_validate({
        "report_type": "strategy",
        "conditional_fields": [{
            "field_name": "行业资金流动",
            "description": "sector fund flow",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "market",
            "value_shape": "array",
            "applicability": "strategy reports",
            "rationale": "observed",
            "priority": 2,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["行业资金流动分析.正向净流入行业"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"行业资金流动分析.正向净流入行业"}
    )
    assert [field.field_name for field in cleaned.conditional_fields] == [
        "市场表现与市场信号"
    ]


def test_report_type_review_cleanup_removes_noise_without_limiting_free_json():
    common = {
        "description": "review candidate",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "relation",
        "value_shape": "object",
        "applicability": "when present",
        "rationale": "observed",
        "priority": 3,
        "source_document_ids": ["d1"],
    }
    cases = [
        ("industry", "估值", "估值.PE"),
        ("industry", "宏观指标", "宏观指标.PMI"),
        ("strategy", "行业重点新闻", "行业重点新闻[0].内容"),
        ("new_stock", "市场表现与估值", "valuation.PE"),
    ]
    for report_type, field_name, path in cases:
        review = CategoryFieldReview.model_validate({
            "report_type": report_type,
            "conditional_fields": [{
                **common,
                "field_name": field_name,
                "observed_json_paths": [path],
            }],
        })
        cleaned = FreeFieldReviewSummariser._validate_sources(
            review, {"d1"}, {path}
        )
        assert cleaned.conditional_fields == []


def test_technology_progress_and_product_features_merge_to_technology_family():
    common = {
        "description": "technology",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "technology",
        "value_shape": "object",
        "applicability": "when present",
        "rationale": "observed",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    for report_type, field_name, path in [
        ("morning_report", "技术进展", "机器人产业与技术进展.核心技术"),
        ("new_stock", "产品分类与技术特点", "产品分类与技术特点.产品"),
    ]:
        review = CategoryFieldReview.model_validate({
            "report_type": report_type,
            "conditional_fields": [{
                **common,
                "field_name": field_name,
                "observed_json_paths": [path],
            }],
        })
        cleaned = FreeFieldReviewSummariser._validate_sources(
            review, {"d1"}, {path}
        )
        assert [field.field_name for field in cleaned.conditional_fields] == [
            "核心技术与技术路线"
        ]


def test_morning_product_and_new_stock_market_forecast_are_generalized():
    common = {
        "description": "business observation",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "relation",
        "value_shape": "object",
        "applicability": "when present",
        "rationale": "observed",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    cases = [
        (
            "morning_report",
            "主要产品或服务",
            "sections.公司研究.main_products",
            "业务板块与主营产品/服务",
        ),
        (
            "new_stock",
            "市场预测",
            "市场预测.全球市场规模.2030",
            "供需格局与驱动",
        ),
    ]
    for report_type, field_name, path, expected in cases:
        review = CategoryFieldReview.model_validate({
            "report_type": report_type,
            "conditional_fields": [{
                **common,
                "field_name": field_name,
                "observed_json_paths": [path],
            }],
        })
        cleaned = FreeFieldReviewSummariser._validate_sources(
            review, {"d1"}, {path}
        )
        assert [field.field_name for field in cleaned.conditional_fields] == [
            expected
        ]


def test_macro_specific_metric_names_merge_and_wrapper_fields_drop():
    common = {
        "description": "宏观",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "MACRO_INDICATOR",
        "value_shape": "object",
        "applicability": "宏观报告",
        "rationale": "输入出现",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "macro",
        "conditional_fields": [
            {**common, "field_name": "地方政府债券净融资额", "observed_json_paths": ["核心观点.地方政府债券净融资额"]},
            {**common, "field_name": "行业利润变化趋势", "observed_json_paths": ["行业分析.工业企业利润变化趋势"]},
            {**common, "field_name": "事件时间", "observed_json_paths": ["核心事件.时间"]},
            {**common, "field_name": "图表信息", "observed_json_paths": ["图表信息.图1"]},
        ],
    })
    paths = {item.observed_json_paths[0] for item in review.conditional_fields}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert [item.field_name for item in cleaned.conditional_fields] == ["宏观经济指标"]


def test_industry_technology_field_requires_semantic_path():
    review = CategoryFieldReview.model_validate({
        "report_type": "industry",
        "conditional_fields": [{
            "field_name": "行业技术应用",
            "description": "技术应用",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "TECH_APPLICATION",
            "value_shape": "array",
            "applicability": "行业",
            "rationale": "输入出现",
            "priority": 2,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["周观点.核心事件[1].内容"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"周观点.核心事件[1].内容"}
    )
    assert cleaned.conditional_fields == []


def test_morning_market_variants_merge_across_documents():
    common = {
        "description": "市场表现",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "signal",
        "value_shape": "object",
        "applicability": "晨会",
        "rationale": "输入出现",
        "priority": 2,
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "morning_report",
        "conditional_fields": [
            {
                **common,
                "field_name": "海外市场指数",
                "source_document_ids": ["d1"],
                "observed_json_paths": ["市场分析.海外市场指数.道琼斯.涨跌幅"],
            },
            {
                **common,
                "field_name": "市场指数表现",
                "source_document_ids": ["d2"],
                "observed_json_paths": ["contents.市场指数.indices[0].change_percent"],
            },
        ],
    })
    paths = {item.observed_json_paths[0] for item in review.conditional_fields}
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review,
        {"d1", "d2"},
        paths,
        {
            "市场分析.海外市场指数.道琼斯.涨跌幅": {"d1"},
            "contents.市场指数.indices[0].change_percent": {"d2"},
        },
    )
    assert [item.field_name for item in cleaned.conditional_fields] == [
        "市场表现与市场信号"
    ]
    assert cleaned.conditional_fields[0].source_document_ids == ["d1", "d2"]


def test_latest_macro_and_morning_fragments_merge_to_reusable_families():
    common = {
        "description": "字段",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "analysis",
        "value_shape": "object",
        "applicability": "报告",
        "rationale": "输入出现",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    macro = CategoryFieldReview.model_validate({
        "report_type": "macro",
        "conditional_fields": [
            {**common, "field_name": "操作机制分析", "observed_json_paths": ["操作机制分析.借债"]},
            {**common, "field_name": "政策意图", "observed_json_paths": ["政策背景与市场预期.政策意图"]},
            {**common, "field_name": "政策期望区间", "observed_json_paths": ["政策背景与市场预期.政策期望区间"]},
        ],
    })
    macro_paths = {item.observed_json_paths[0] for item in macro.conditional_fields}
    cleaned_macro = FreeFieldReviewSummariser._validate_sources(
        macro, {"d1"}, macro_paths
    )
    assert [item.field_name for item in cleaned_macro.conditional_fields] == [
        "政策事件及影响"
    ]

    morning = CategoryFieldReview.model_validate({
        "report_type": "morning_report",
        "conditional_fields": [
            {**common, "field_name": "市场热点概念", "observed_json_paths": ["市场分析.概念热点"]},
            {**common, "field_name": "市场技术分析", "observed_json_paths": ["市场分析.技术指标"]},
            {**common, "field_name": "市场预期", "observed_json_paths": ["市场分析.预期"]},
            {**common, "field_name": "行业投资建议", "observed_json_paths": ["重点推荐.行业投资建议"]},
        ],
    })
    morning_paths = {item.observed_json_paths[0] for item in morning.conditional_fields}
    cleaned_morning = FreeFieldReviewSummariser._validate_sources(
        morning, {"d1"}, morning_paths
    )
    assert [item.field_name for item in cleaned_morning.conditional_fields] == [
        "市场表现与市场信号",
        "投资建议/评级",
    ]


def test_market_volatility_risk_merges_into_general_risk_family():
    review = CategoryFieldReview.model_validate({
        "report_type": "morning_report",
        "conditional_fields": [{
            "field_name": "市场波动风险",
            "description": "市场风险",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "RISK",
            "value_shape": "array",
            "applicability": "晨会",
            "rationale": "输入出现",
            "priority": 2,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["市场分析.风险.市场波动风险"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"市场分析.风险.市场波动风险"}
    )
    assert [item.field_name for item in cleaned.conditional_fields] == [
        "关键风险与传导"
    ]


def test_canonical_merge_keeps_one_evidence_path_per_source_document():
    common = {
        "description": "市场",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "signal",
        "value_shape": "object",
        "applicability": "晨会",
        "rationale": "输入出现",
        "priority": 2,
    }
    fields = [
        GeneralFieldRecommendation(
            **common,
            field_name="海外市场指数",
            source_document_ids=["d1"],
            observed_json_paths=["市场.海外指数.涨跌"],
        ),
        GeneralFieldRecommendation(
            **common,
            field_name="市场指数表现",
            source_document_ids=["d2"],
            observed_json_paths=["市场指数.涨跌"],
        ),
        GeneralFieldRecommendation(
            **common,
            field_name="市场涨跌幅",
            source_document_ids=["d3"],
            observed_json_paths=["市场表现.涨跌幅"],
        ),
    ]
    review = CategoryFieldReview(
        report_type="morning_report", conditional_fields=fields
    )
    path_docs = {
        "市场.海外指数.涨跌": {"d1"},
        "市场指数.涨跌": {"d2"},
        "市场表现.涨跌幅": {"d3"},
    }
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1", "d2", "d3"}, set(path_docs), path_docs
    )
    field = cleaned.conditional_fields[0]
    assert field.field_name == "市场表现与市场信号"
    assert field.source_document_ids == ["d1", "d2", "d3"]
    assert len(field.observed_json_paths) == 3


def test_reviewer_rejects_financial_and_investment_fields_with_wrong_evidence():
    common = {
        "description": "字段",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "analysis",
        "value_shape": "object",
        "applicability": "公司研报",
        "rationale": "输入出现",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "stock",
        "reviewed_document_count": 1,
        "conditional_fields": [
            {
                **common,
                "field_name": "财务预测",
                "observed_json_paths": ["煤炭业务.迎峰度夏补库需求"],
            },
            {
                **common,
                "field_name": "投资建议",
                "observed_json_paths": ["风险提示.新能源降本不及预期"],
            },
        ],
    })
    paths = {"煤炭业务.迎峰度夏补库需求", "风险提示.新能源降本不及预期"}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert cleaned.conditional_fields == []


def test_cooperation_field_drops_unrelated_product_migration_path():
    review = CategoryFieldReview.model_validate({
        "report_type": "stock",
        "conditional_fields": [{
            "field_name": "合作与投资",
            "description": "合作",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "COOPERATION",
            "value_shape": "array",
            "applicability": "公司事件",
            "rationale": "输入出现",
            "priority": 2,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["公司业务进展.鸿蒙化改造"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"公司业务进展.鸿蒙化改造"}
    )
    assert cleaned.conditional_fields == []


def test_core_support_must_link_each_document_to_an_observed_path():
    review = CategoryFieldReview.model_validate({
        "report_type": "stock",
        "core_fields": [{
            "field_name": "产业链定位",
            "description": "公司所处环节",
            "scope": "CORE",
            "knowledge_graph_role": "INDUSTRY_CHAIN_POSITION",
            "value_shape": "string",
            "applicability": "公司研报",
            "rationale": "模型声称两篇支持",
            "priority": 1,
            "source_document_ids": ["d1", "d2"],
            "observed_json_paths": ["新能源业务.布局.产业链"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review,
        {"d1", "d2"},
        {"新能源业务.布局.产业链"},
        {"新能源业务.布局.产业链": {"d1"}},
    )
    assert cleaned.core_fields == []
    assert cleaned.conditional_fields[0].source_document_ids == ["d1"]


def test_core_technology_does_not_use_a_production_line_as_technology_evidence():
    review = CategoryFieldReview.model_validate({
        "report_type": "stock",
        "core_fields": [{
            "field_name": "核心技术",
            "description": "技术能力",
            "scope": "CORE",
            "knowledge_graph_role": "TECHNOLOGY_CAPABILITY",
            "value_shape": "array",
            "applicability": "公司研报",
            "rationale": "输入出现",
            "priority": 2,
            "source_document_ids": ["d1", "d2"],
            "observed_json_paths": [
                "新能源业务.项目进展.新型储能产品智能生产线",
                "公司业务与产品.核心技术",
            ],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review,
        {"d1", "d2"},
        {
            "新能源业务.项目进展.新型储能产品智能生产线",
            "公司业务与产品.核心技术",
        },
        {
            "新能源业务.项目进展.新型储能产品智能生产线": {"d1"},
            "公司业务与产品.核心技术": {"d2"},
        },
    )
    assert cleaned.core_fields == []
    assert cleaned.conditional_fields[0].source_document_ids == ["d2"]


def test_operating_metric_rejects_market_holding_evidence():
    review = CategoryFieldReview.model_validate({
        "report_type": "industry",
        "conditional_fields": [{
            "field_name": "关键经营指标",
            "description": "运营指标",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "OPERATING_METRIC",
            "value_shape": "array",
            "applicability": "行业报告",
            "rationale": "输入出现",
            "priority": 1,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["行业周报.沪深港通持股金额"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"行业周报.沪深港通持股金额"}
    )
    assert cleaned.conditional_fields == []


def test_strategy_policy_background_and_impact_are_merged():
    common = {
        "description": "政策",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "policy",
        "value_shape": "array",
        "applicability": "策略报告",
        "rationale": "输入出现",
        "priority": 1,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "strategy",
        "reviewed_document_count": 1,
        "conditional_fields": [
            {**common, "field_name": "政策背景", "observed_json_paths": ["政策背景.新规"]},
            {**common, "field_name": "政策影响", "observed_json_paths": ["政策影响.未来定位"]},
        ],
    })
    paths = {"政策背景.新规", "政策影响.未来定位"}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert [item.field_name for item in cleaned.conditional_fields] == ["政策事件及影响"]


def test_morning_report_fragments_merge_and_information_source_is_removed():
    common = {
        "description": "晨会字段",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "signal",
        "value_shape": "string",
        "applicability": "晨会",
        "rationale": "输入出现",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "morning_report",
        "reviewed_document_count": 1,
        "conditional_fields": [
            {**common, "field_name": "货币政策方向", "observed_json_paths": ["晨会.货币政策方向"]},
            {**common, "field_name": "重点支持领域", "observed_json_paths": ["晨会.重点支持领域"]},
            {**common, "field_name": "市场表现", "observed_json_paths": ["晨会.市场表现"]},
            {**common, "field_name": "市场技术指标", "observed_json_paths": ["晨会.市场技术指标"]},
            {**common, "field_name": "宏观经济环境", "observed_json_paths": ["晨会.宏观经济环境"]},
            {**common, "field_name": "信息来源", "observed_json_paths": ["晨会.信息来源"]},
        ],
    })
    paths = {item.observed_json_paths[0] for item in review.conditional_fields}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert [item.field_name for item in cleaned.conditional_fields] == [
        "宏观环境与风险",
        "市场表现与市场信号",
        "政策事件及影响",
    ]


def test_morning_market_field_drops_policy_only_evidence_before_merging():
    review = CategoryFieldReview.model_validate({
        "report_type": "morning_report",
        "reviewed_document_count": 1,
        "conditional_fields": [{
            "field_name": "行业表现",
            "description": "市场表现",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "signal",
            "value_shape": "object",
            "applicability": "晨会",
            "rationale": "输入出现",
            "priority": 2,
            "source_document_ids": ["d1"],
            "observed_json_paths": ["重点推荐.金股组合.政策背景"],
        }],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"重点推荐.金股组合.政策背景"}
    )
    assert cleaned.conditional_fields == []


def test_field_reviewer_drops_metadata_and_metadata_only_evidence():
    common = {
        "description": "字段",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "metadata",
        "value_shape": "object",
        "applicability": "研报",
        "rationale": "输入出现",
        "priority": 5,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "industry",
        "conditional_fields": [
            {**common, "field_name": "分析师信息", "observed_json_paths": ["分析师.姓名"]},
            {**common, "field_name": "行业动态", "observed_json_paths": ["免责声明.内容"]},
        ],
    })
    cleaned = FreeFieldReviewSummariser._validate_sources(
        review, {"d1"}, {"分析师.姓名", "免责声明.内容"}
    )
    assert cleaned.conditional_fields == []


def test_field_reviewer_drops_semantically_mismatched_graph_evidence():
    common = {
        "description": "图谱字段",
        "scope": "CORE",
        "knowledge_graph_role": "relation",
        "value_shape": "array",
        "applicability": "行业报告",
        "rationale": "候选关系",
        "priority": 2,
        "source_document_ids": ["d1", "d2"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "industry",
        "reviewed_document_count": 2,
        "core_fields": [
            {
                **common,
                "field_name": "供需驱动",
                "observed_json_paths": ["ETF动态.美国比特币现货ETF净流入"],
            },
            {
                **common,
                "field_name": "产业链定位",
                "observed_json_paths": ["风险提示.行业竞争加剧.影响对象"],
            },
            {
                **common,
                "field_name": "竞争格局",
                "observed_json_paths": ["风险提示.行业竞争加剧.影响对象"],
            },
        ],
    })
    paths = {
        "ETF动态.美国比特币现货ETF净流入",
        "风险提示.行业竞争加剧.影响对象",
    }
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1", "d2"}, paths)
    assert [item.field_name for item in cleaned.core_fields] == ["竞争格局与竞争关系"]
    assert cleaned.coverage_gaps


@pytest.mark.asyncio
async def test_cross_document_reviewer_generalizes_specific_metrics():
    class ReviewerLLM:
        model_id = "fake-reviewer"

        async def complete_text(self, **kwargs):
            assert kwargs["response_schema"]["properties"]["core_fields"]
            payload = json.loads(kwargs["extracted_text"])
            ids = [item["document_id"] for item in payload["documents"]]
            return json.dumps({
                "report_type": "stock",
                "reviewed_document_count": 2,
                "core_fields": [{
                    "field_name": "主营产品与服务",
                    "description": "公司向市场提供的主要产品和服务",
                    "scope": "CORE",
                    "knowledge_graph_role": "COMPANY-PRODUCES-PRODUCT",
                    "value_shape": "[{name,category,description}]",
                    "applicability": "所有公司研报",
                    "rationale": "跨行业刻画产业链供给端",
                    "priority": 1,
                    "source_document_ids": ids,
                    "observed_json_paths": ["业务.产品", "产业链.供给产品"],
                    "example_values": ["交换机芯片", "煤炭流通服务"],
                }],
                "conditional_fields": [{
                    "field_name": "关键经营指标",
                    "description": "行业或业务特有的量化经营指标集合",
                    "scope": "CONDITIONAL",
                    "knowledge_graph_role": "ENTITY-HAS_METRIC-METRIC_VALUE",
                    "value_shape": "[{metric_name,period,value,unit,business_segment}]",
                    "applicability": "文档披露行业特有运营指标时",
                    "rationale": "统一容纳产量、处理量、出货量等指标",
                    "priority": 3,
                    "source_document_ids": ids,
                    "observed_json_paths": ["经营.污泥处理量", "经营.芯片出货量"],
                    "example_values": ["污泥处理量74.97万吨"],
                }],
                "rejected_over_specific_fields": [{
                    "observed_field": "污泥处理量",
                    "reason": "仅适用于具体业务，不能成为跨行业模板字段",
                    "generalized_to": "关键经营指标",
                    "source_document_ids": [ids[0]],
                }],
                "document_type_insights": ["公司深度更适合发现产业链关系"],
                "coverage_gaps": [],
            }, ensure_ascii=False)

    results = [
        FreeExtractionResult(
            document_id="d1",
            report_type="stock",
            content={"经营": {"污泥处理量": "74.97万吨"}, "业务": {"产品": "煤炭服务"}},
        ),
        FreeExtractionResult(
            document_id="d2",
            report_type="stock",
            content={"产业链": {"供给产品": "交换机芯片"}, "经营": {"芯片出货量": "增长"}},
        ),
    ]
    review = await FreeFieldReviewSummariser(ReviewerLLM()).summarise("stock", results)
    assert [field.field_name for field in review.core_fields] == [
        "业务板块与主营产品/服务"
    ]
    assert [field.field_name for field in review.conditional_fields] == ["关键经营指标"]
    assert review.rejected_over_specific_fields[0].observed_field == "污泥处理量"


def test_english_path_fragments_are_generalized_for_reusable_profiles():
    common = {
        "description": "sample field",
        "scope": "CONDITIONAL",
        "knowledge_graph_role": "raw",
        "value_shape": "string",
        "applicability": "research report",
        "rationale": "observed",
        "priority": 2,
        "source_document_ids": ["d1"],
    }
    review = CategoryFieldReview.model_validate({
        "report_type": "industry",
        "conditional_fields": [
            {**common, "field_name": "industry_overview.period", "observed_json_paths": ["industry_overview.period"]},
            {**common, "field_name": "industry_overview.status", "observed_json_paths": ["industry_overview.status"]},
            {**common, "field_name": "industry_challenges.factors", "observed_json_paths": ["industry_challenges.factors"]},
        ],
    })
    paths = {"industry_overview.period", "industry_overview.status", "industry_challenges.factors"}
    cleaned = FreeFieldReviewSummariser._validate_sources(review, {"d1"}, paths)
    assert [field.field_name for field in cleaned.conditional_fields] == [
        "关键风险与传导", "行业状态与驱动"
    ]

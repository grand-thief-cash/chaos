from scripts.build_sampling_field_catalog import _deterministic_proposal, _validate_catalog
from atlas.models.free_extraction import SamplingFieldCatalogProposal


def test_catalog_derives_provenance_and_demotes_single_document_field():
    proposal = SamplingFieldCatalogProposal.model_validate({
        "fields": [{
            "field_name": "上下游关系",
            "description": "供应与客户关系",
            "scope": "CORE",
            "knowledge_graph_role": "SUPPLY_CHAIN_RELATION",
            "value_shape": "array",
            "applicability": "stock/industry",
            "priority": 1,
            "source_field_ids": ["stock:上下游"],
        }],
    })
    result = _validate_catalog(proposal, {
        "stock:上下游": {
            "report_type": "stock",
            "evidence_document_ids": ["d1"],
            "observed_json_paths": ["收购影响.客户拓展"],
        }
    })
    assert result["fields"][0]["scope"] == "CONDITIONAL"
    assert result["fields"][0]["applicable_report_types"] == ["stock"]
    assert result["fields"][0]["evidence_document_ids"] == ["d1"]
    assert result["fields"][0]["evidence_grade"] == "PROVISIONAL"
    assert result["extraction_profiles"]["stock"][0]["field_name"] == "上下游关系"
    assert any("单文档证据" in gap for gap in result["coverage_gaps"])


def test_catalog_rejects_unknown_source_and_specific_name():
    proposal = SamplingFieldCatalogProposal.model_validate({
        "fields": [
            {
                "field_name": "污泥处理量",
                "description": "过细指标",
                "scope": "CONDITIONAL",
                "knowledge_graph_role": "METRIC",
                "value_shape": "number",
                "applicability": "单一公司",
                "priority": 5,
                "source_field_ids": ["known"],
            },
            {
                "field_name": "产业链定位",
                "description": "所处环节",
                "scope": "CORE",
                "knowledge_graph_role": "CHAIN_POSITION",
                "value_shape": "string",
                "applicability": "公司研报",
                "priority": 1,
                "source_field_ids": ["unknown"],
            },
        ]
    })
    result = _validate_catalog(proposal, {
        "known": {
            "report_type": "stock",
            "evidence_document_ids": ["d1"],
            "observed_json_paths": ["经营.污泥处理量"],
        }
    })
    assert result["fields"] == []


def test_catalog_merges_market_and_investment_families_and_restores_metric():
    proposal = SamplingFieldCatalogProposal.model_validate({
        "fields": [
            {
                "field_name": "市场表现",
                "description": "市场",
                "scope": "CONDITIONAL",
                "knowledge_graph_role": "SIGNAL",
                "value_shape": "object",
                "applicability": "行业",
                "priority": 2,
                "source_field_ids": ["market-industry"],
            },
            {
                "field_name": "市场表现与市场信号",
                "description": "市场",
                "scope": "CONDITIONAL",
                "knowledge_graph_role": "SIGNAL",
                "value_shape": "object",
                "applicability": "晨会",
                "priority": 2,
                "source_field_ids": ["market-morning"],
            },
            {
                "field_name": "投资建议",
                "description": "建议",
                "scope": "CONDITIONAL",
                "knowledge_graph_role": "VIEW",
                "value_shape": "object",
                "applicability": "策略",
                "priority": 4,
                "source_field_ids": ["advice-strategy"],
            },
        ]
    })
    sources = {
        "market-industry": {"report_type": "industry", "field_name": "市场表现", "scope": "CONDITIONAL", "description": "市场", "knowledge_graph_role": "SIGNAL", "value_shape": "object", "applicability": "行业", "evidence_document_ids": ["d1"], "observed_json_paths": ["市场.涨跌"]},
        "market-morning": {"report_type": "morning_report", "field_name": "市场表现与市场信号", "scope": "CONDITIONAL", "description": "市场", "knowledge_graph_role": "SIGNAL", "value_shape": "object", "applicability": "晨会", "evidence_document_ids": ["d2"], "observed_json_paths": ["指数.涨跌"]},
        "advice-strategy": {"report_type": "strategy", "field_name": "投资建议", "scope": "CONDITIONAL", "description": "建议", "knowledge_graph_role": "VIEW", "value_shape": "object", "applicability": "策略", "evidence_document_ids": ["d3"], "observed_json_paths": ["投资建议"]},
        "advice-industry": {"report_type": "industry", "field_name": "投资建议/评级", "scope": "CONDITIONAL", "description": "建议", "knowledge_graph_role": "VIEW", "value_shape": "object", "applicability": "行业", "evidence_document_ids": ["d4"], "observed_json_paths": ["投资评级"]},
        "metric": {"report_type": "stock", "field_name": "关键经营指标", "scope": "CONDITIONAL", "description": "指标", "knowledge_graph_role": "METRIC", "value_shape": "array", "applicability": "披露时", "evidence_document_ids": ["d5"], "observed_json_paths": ["经营.收入"]},
    }
    result = _validate_catalog(proposal, sources)
    by_name = {item["field_name"]: item for item in result["fields"]}
    assert set(by_name) == {"市场表现与市场信号", "投资建议与评级", "关键经营指标"}
    assert by_name["市场表现与市场信号"]["applicable_report_types"] == [
        "industry", "morning_report"
    ]
    assert by_name["投资建议与评级"]["applicable_report_types"] == [
        "industry", "strategy"
    ]


def test_catalog_restores_evidence_backed_supply_and_technology_relations():
    proposal = SamplingFieldCatalogProposal.model_validate({
        "fields": [{
            "field_name": "政策事件及影响",
            "description": "政策",
            "scope": "CONDITIONAL",
            "knowledge_graph_role": "POLICY",
            "value_shape": "array",
            "applicability": "行业",
            "priority": 1,
            "source_field_ids": ["policy"],
        }]
    })
    sources = {
        "policy": {"report_type": "industry", "field_name": "政策事件及影响", "scope": "CONDITIONAL", "description": "政策", "knowledge_graph_role": "POLICY", "value_shape": "array", "applicability": "行业", "evidence_document_ids": ["d1"], "observed_json_paths": ["政策.影响"]},
        "supply": {"report_type": "industry", "field_name": "供需格局", "scope": "CONDITIONAL", "description": "供需", "knowledge_graph_role": "SUPPLY_DEMAND", "value_shape": "object", "applicability": "行业", "evidence_document_ids": ["d2"], "observed_json_paths": ["锡.供需预期.供需格局"]},
        "technology": {"report_type": "industry", "field_name": "行业技术应用", "scope": "CONDITIONAL", "description": "技术应用", "knowledge_graph_role": "TECH_APPLICATION", "value_shape": "array", "applicability": "行业", "evidence_document_ids": ["d3"], "observed_json_paths": ["周观点.核心事件.技术应用"]},
    }
    result = _validate_catalog(proposal, sources)
    names = {item["field_name"] for item in result["fields"]}
    assert "供需格局与驱动" in names
    assert "产品/技术/应用关系" in names


def test_catalog_restores_all_audited_reusable_families_omitted_by_final_llm():
    proposal = SamplingFieldCatalogProposal.model_validate({
        "fields": [{
            "field_name": "关键风险与传导",
            "description": "risk",
            "scope": "CORE",
            "knowledge_graph_role": "RISK",
            "value_shape": "array",
            "applicability": "all",
            "priority": 1,
            "source_field_ids": ["risk"],
        }]
    })
    sources = {
        "risk": {"report_type": "stock", "field_name": "关键风险与传导", "scope": "CORE", "evidence_document_ids": ["d1", "d2"], "observed_json_paths": ["风险提示"]},
        "macro": {"report_type": "macro", "field_name": "宏观经济指标", "scope": "CONDITIONAL", "evidence_document_ids": ["d3", "d4"], "observed_json_paths": ["宏观指标.PMI"]},
        "market": {"report_type": "strategy", "field_name": "市场表现与市场信号", "scope": "CONDITIONAL", "evidence_document_ids": ["d5", "d6"], "observed_json_paths": ["市场表现.涨跌"]},
        "advice": {"report_type": "strategy", "field_name": "投资建议/评级", "scope": "CONDITIONAL", "evidence_document_ids": ["d7", "d8"], "observed_json_paths": ["投资建议"]},
        "finance": {"report_type": "stock", "field_name": "财务与盈利预测", "scope": "CONDITIONAL", "evidence_document_ids": ["d9", "d10"], "observed_json_paths": ["盈利预测.净利润"]},
        "capacity": {"report_type": "stock", "field_name": "产能与项目布局", "scope": "CONDITIONAL", "evidence_document_ids": ["d11"], "observed_json_paths": ["项目布局.产能"]},
    }
    result = _validate_catalog(proposal, sources)
    names = {field["field_name"] for field in result["fields"]}
    assert names == {
        "关键风险与传导",
        "宏观经济指标",
        "市场表现与市场信号",
        "投资建议与评级",
        "财务与盈利预测",
        "产能与项目布局",
    }


def test_deterministic_catalog_fallback_preserves_evidence_backed_source():
    sources = {
        "new-stock-tech": {
            "report_type": "new_stock",
            "field_name": "核心技术与技术路线",
            "scope": "CORE",
            "description": "核心技术",
            "knowledge_graph_role": "TECHNOLOGY",
            "value_shape": "array",
            "applicability": "新股报告披露技术时",
            "evidence_document_ids": ["d1", "d2"],
            "observed_json_paths": ["产品与技术.技术优势", "products.tech_features"],
        }
    }
    proposal = _deterministic_proposal(sources)
    assert proposal.review_notes == "deterministic_catalog_fallback"
    result = _validate_catalog(proposal, sources)
    assert result["fields"][0]["field_name"] == "核心技术与研发能力"
    assert result["extraction_profiles"]["new_stock"][0]["field_name"] == "核心技术与研发能力"

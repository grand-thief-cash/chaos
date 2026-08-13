from scripts.audit_sampling_run import audit_category
from scripts.rereview_sampling_run import _evidence_complete


def _field(name: str, scope: str = "CONDITIONAL") -> dict:
    return {
        "field_name": name,
        "scope": scope,
        "priority": 1,
        "knowledge_graph_role": "COMPANY-PRODUCES-PRODUCT",
        "value_shape": "[{name,category}]",
        "evidence_document_ids": ["d1"],
        "observed_json_paths": ["公司.主营产品"],
    }


def _category(field: dict) -> dict:
    scope = field["scope"]
    return {
        "report_type": "stock",
        "raw_results": [{
            "document_id": "d1",
            "title": "公司深度",
            "free_extraction_result": {
                "readability": "READABLE",
                "content": {"公司": {"主营产品": ["交换机芯片"]}},
                "quality_issues": [],
            },
        }],
        "field_summary": {
            "review_method": "llm_cross_document_generalization_v1",
            "core_fields": [field] if scope == "CORE" else [],
            "conditional_fields": [field] if scope == "CONDITIONAL" else [],
        },
    }


def _two_document_core_category(field: dict) -> dict:
    category = _category(field)
    category["raw_results"].append({
        "document_id": "d2",
        "title": "第二篇公司深度",
        "free_extraction_result": {
            "readability": "READABLE",
            "content": {"业务": {"主营产品": ["工业软件"]}},
            "quality_issues": [],
        },
    })
    field["evidence_document_ids"] = ["d1", "d2"]
    field["observed_json_paths"] = ["公司.主营产品", "业务.主营产品"]
    return category


def test_business_audit_accepts_generalized_provenanced_field():
    result = audit_category(_category(_field("主营产品与服务")))
    assert result["passed"]
    assert result["documents"][0]["top_level_keys"] == ["公司"]


def test_business_audit_rejects_legacy_and_period_specific_fields():
    category = _category(_field("每股收益-最新股本摊薄_E"))
    category["raw_results"][0]["free_extraction_result"]["content"] = {
        "candidate_fields": []
    }
    result = audit_category(category)
    assert not result["passed"]
    assert any("legacy candidate_fields" in item for item in result["hard_failures"])
    assert any("suffix" in item for item in result["hard_failures"])


def test_business_audit_rejects_single_document_core_field():
    result = audit_category(_category(_field("主营产品与服务", "CORE")))
    assert not result["passed"]
    assert any("single-document" in item for item in result["hard_failures"])
    assert any("cross-document evidence" in item for item in result["hard_failures"])


def test_business_audit_rejects_unlinked_claimed_source():
    category = _two_document_core_category(_field("主营产品与服务", "CORE"))
    category["field_summary"]["core_fields"][0]["observed_json_paths"] = [
        "公司.主营产品"
    ]
    result = audit_category(category)
    assert not result["passed"]
    assert any("not linked" in item for item in result["hard_failures"])


def test_business_audit_rejects_raw_json_path_as_final_field_name():
    result = audit_category(_category(_field("financial_forecasts.unit")))
    assert not result["passed"]
    assert any("raw JSON path" in item for item in result["hard_failures"])


def test_existing_review_filter_is_idempotent_after_evidence_is_removed():
    valid = _field("主营产品与服务")
    invalid = {**_field("市场表现"), "evidence_document_ids": [], "observed_json_paths": []}
    fields = _evidence_complete([valid, invalid], "CONDITIONAL")
    assert [field["field_name"] for field in fields] == ["主营产品与服务"]

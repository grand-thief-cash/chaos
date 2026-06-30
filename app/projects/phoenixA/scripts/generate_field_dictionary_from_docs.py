#!/usr/bin/env python3
"""Generate AmazingData field dictionary source files (JSONL).

This script is the cross-platform source of truth for:
  - scripts/field_dictionary/amazing_data/*.jsonl
  - scripts/field_dictionary/amazing_data/datasets.json

It bootstraps most fields from docs/tables_description and applies a curated
set of SDK-based corrections for metadata placement, units, enums and aliases.

It does NOT generate the seed SQL migration. After running this script to
refresh the JSONL sources, run regenerate_seed_sql.py (in the same directory)
to produce migrations/postgresql/security/0004_govern_seed.sql.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "2026-06-27"
SOURCE = "amazing_data"

FINANCIAL_TYPE_META: dict[str, dict[str, str]] = {
    "balance_sheet": {
        "label": "资产负债表",
        "sdk_section": "3.5.5.1",
        "sdk_function": "get_balance_sheet",
    },
    "cashflow": {
        "label": "现金流量表",
        "sdk_section": "3.5.5.2",
        "sdk_function": "get_cash_flow",
    },
    "income": {
        "label": "利润表",
        "sdk_section": "3.5.5.3",
        "sdk_function": "get_income",
    },
    "profit_express": {
        "label": "业绩快报",
        "sdk_section": "3.5.5.4",
        "sdk_function": "get_profit_express",
    },
    "profit_notice": {
        "label": "业绩预告",
        "sdk_section": "3.5.5.5",
        "sdk_function": "get_profit_notice",
    },
}

CORPORATE_TYPE_META: dict[str, dict[str, str]] = {
    "dividend": {
        "label": "分红数据",
        "sdk_section": "3.5.7.1",
        "sdk_function": "get_dividend",
    },
    "right_issue": {
        "label": "配股数据",
        "sdk_section": "3.5.7.2",
        "sdk_function": "get_right_issue",
    },
}

TOP_LEVEL_FINANCIAL = {
    "MARKET_CODE": "symbol",
    "SECURITY_NAME": "security_name",
    "STATEMENT_TYPE": "statement_code",
    "REPORT_TYPE": "report_type",
    "REPORTING_PERIOD": "reporting_period",
    "ANN_DATE": "ann_date",
    "ACTUAL_ANN_DATE": "actual_ann_date",
    "COMP_TYPE_CODE": "comp_type_code",
}

TOP_LEVEL_CORPORATE = {
    "MARKET_CODE": "symbol",
    "ANN_DATE": "ann_date",
    "REPORT_PERIOD": "report_period",
    "RIGHTSISSUE_YEAR": "report_period",
    "DIV_PROGRESS": "progress_code",
    "PROGRESS": "progress_code",
}

TOP_LEVEL_EQUITY = {
    "MARKET_CODE": "symbol",
    "ANN_DATE": "ann_date",
    "CHANGE_DATE": "change_date",
}

DATE_FIELDS = {
    "REPORTING_PERIOD",
    "ANN_DATE",
    "ACTUAL_ANN_DATE",
    "FIRST_ANN_DATE",
    "DATE_EQY_RECORD",
    "DATE_EX",
    "DATE_DVD_PAYOUT",
    "LISTINGDATE_OF_DVD_SHR",
    "DIV_PRELANDATE",
    "DIV_SMTGDATE",
    "DATE_DVD_ANN",
    "DIV_BASEDATE",
    "DIV_PREANN_DATE",
    "SHAREB_REG_DATE",
    "EX_DIVIDEND_DATE",
    "LISTED_DATE",
    "PAY_START_DATE",
    "PAY_END_DATE",
    "PREPLAN_DATE",
    "SMTG_ANN_DATE",
    "PASS_DATE",
    "APPROVED_DATE",
    "EXECUTE_DATE",
    "RESULT_DATE",
    "LIST_ANN_DATE",
    "CHANGE_DATE",
    "EX_CHANGE_DATE",
}

ENUM_REFS = {
    "STATEMENT_TYPE": "STATEMENT_TYPE",
    "REPORT_TYPE": "REPORT_TYPE",
    "COMP_TYPE_CODE": "COMP_TYPE_CODE",
    "DIV_PROGRESS": "DIV_PROGRESS",
    "PROGRESS": "PROGRESS",
    "P_TYPECODE": "P_TYPECODE",
    "IS_AUDIT": "BOOLEAN_FLAG",
    "IS_CHANGED": "BOOLEAN_FLAG",
    "IS_CALCULATION": "BOOLEAN_FLAG",
    "CURRENT_SIGN": "BOOLEAN_FLAG",
    "IS_VALID": "BOOLEAN_FLAG",
}

STRING_FIELDS = {"CURRENCY_CODE"}

CORE_FIELDS: dict[str, set[str]] = {
    "balance_sheet": {
        "TOTAL_ASSETS",
        "TOTAL_LIAB",
        "TOTAL_CUR_ASSETS",
        "TOTAL_CUR_LIAB",
        "TOT_SHARE_EQUITY_EXCL_MIN_INT",
        "TOT_SHARE",
        "CURRENCY_CAP",
        "INV",
        "GOODWILL",
    },
    "income": {
        "TOT_OPERA_REV",
        "OPERA_REV",
        "OPERA_PROFIT",
        "TOTAL_PROFIT",
        "NET_PRO_EXCL_MIN_INT_INC",
        "NET_PRO_INCL_MIN_INT_INC",
        "BASIC_EPS",
        "DILUTED_EPS",
        "EBIT",
        "EBITDA",
    },
    "cashflow": {
        "NET_CASH_FLOW_OPERA_ACT",
        "NET_CASH_FLOW_INV_ACT",
        "NET_CASH_FLOW_FIN_ACT",
        "IND_NET_CASH_FLOWS_OPERA_ACT",
        "FREE_CASH_FLOW",
        "CASH_RECP_SG_AND_RS",
        "NET_PROFIT",
    },
    "profit_express": {
        "TOTAL_ASSETS",
        "NET_PRO_EXCL_MIN_INT_INC",
        "TOT_OPERA_REV",
        "TOTAL_PROFIT",
        "OPERA_PROFIT",
        "EPS_BASIC",
        "TOT_SHARE_EQUITY_EXCL_MIN_INT",
        "IS_AUDIT",
        "ROE_WEIGHTED",
        "PERFORMANCE_SUMMARY",
        "NET_ASSET_PS",
    },
    "profit_notice": {
        "P_TYPECODE",
        "P_CHANGE_MAX",
        "P_CHANGE_MIN",
        "NET_PROFIT_MAX",
        "NET_PROFIT_MIN",
        "FIRST_ANN_DATE",
        "P_REASON",
        "P_SUMMARY",
        "P_NET_PARENT_FIRM",
    },
    "dividend": {
        "DIV_PROGRESS",
        "DVD_PER_SHARE_STK",
        "DVD_PER_SHARE_PRE_TAX_CASH",
        "DVD_PER_SHARE_AFTER_TAX_CASH",
        "DATE_EQY_RECORD",
        "DATE_EX",
        "DATE_DVD_PAYOUT",
        "DIV_BASESHARE",
    },
    "right_issue": {
        "PROGRESS",
        "PRICE",
        "RATIO",
        "AMT_PLAN",
        "AMT_REAL",
        "COLLECTION_FUND",
        "SHAREB_REG_DATE",
        "EX_DIVIDEND_DATE",
    },
    "equity_structure": {
        "TOT_SHARE",
        "FLOAT_SHARE",
        "FLOAT_A_SHARE",
        "FLOAT_B_SHARE",
        "TOT_TRADABLE_SHARE",
        "RESTRICTED_A_SHARE",
        "TOT_RESTRICTED_SHARE",
    },
}

ALIASES = {
    "NET_CASH_FLOW_OPERA_ACT": ["NET_CASH_FLOWS_OPERA_ACT"],
    "NET_CASH_FLOW_INV_ACT": ["NET_CASH_FLOWS_INV_ACT"],
    "NET_CASH_FLOW_FIN_ACT": ["NET_CASH_FLOWS_FIN_ACT"],
    "EPS_BASIC": ["BASIC_EPS"],
}

EQUITY_RAW_FIELDS: list[tuple[str, str, str, str]] = [
    ("MARKET_CODE", "string", "证券代码", "映射到表 symbol"),
    ("ANN_DATE", "string", "公告日期", "映射到表 ann_date"),
    ("CHANGE_DATE", "string", "变动日期", "映射到表 change_date"),
    ("SHARE_CHANGE_REASON_STR", "string", "股本变动原因描述", "PDF Markdown 断行为 SHARE_CHANGE_REA SON_STR，已校正"),
    ("EX_CHANGE_DATE", "string", "除权日期", "股票分红送转股时的除权日；股票增发时的登记日"),
    ("CURRENT_SIGN", "int", "最新标志", "1:是 0:否"),
    ("IS_VALID", "int", "是否有效", "1:是 0:否"),
    ("TOT_SHARE", "float", "总股本", "万股"),
    ("FLOAT_SHARE", "float", "流通股", "万股"),
    ("FLOAT_A_SHARE", "float", "流通 A 股", "万股"),
    ("FLOAT_B_SHARE", "float", "流通 B 股", "万股"),
    ("FLOAT_HK_SHARE", "float", "香港流通股", "万股"),
    ("FLOAT_OS_SHARE", "float", "海外流通股", "万股"),
    ("TOT_TRADABLE_SHARE", "float", "流通股合计", "PDF Markdown 断行为 TOT_TRADABLE_SHA RE，已校正"),
    ("RTD_A_SHARE_INST", "float", "限售 A 股(其他内资持股:机构配售股)", "万股"),
    ("RTD_A_SHARE_DOMESNP", "float", "限售 A 股(其他内资持股:境内自然人持股)", "万股"),
    ("RTD_SHARE_SENIOR", "float", "限售股份(高管持股)", "万股"),
    ("RTD_A_SHARE_FOREIGN", "float", "限售 A 股(外资持股)", "万股"),
    ("RTD_A_SHARE_FORJUR", "float", "限售 A 股(境外法人持股)", "万股"),
    ("RTD_A_SHARE_FORNP", "float", "限售 A 股(境外自然人持股)", "万股"),
    ("RESTRICTED_B_SHARE", "float", "限售 B 股", "万股"),
    ("OTHER_RTD_SHARE", "float", "其他限售股", "万股"),
    ("NON_TRADABLE_SHARE", "float", "非流通股", "万股"),
    ("NTRD_SHARE_STATE_PCT", "float", "非流通股(国有股)", "万股"),
    ("NTRD_SHARE_STATE", "float", "非流通股(国家股)", "万股"),
    ("NTRD_SHARE_STATEJUR", "float", "非流通股(国有法人股)", "万股"),
    ("NTRD_SHARE_DOMESJUR", "float", "非流通股(境内法人股)", "万股"),
    ("NTRD_SHARE_DOMES_INITIATOR", "float", "非流通股(境内法人股:境内发起人股)", "万股"),
    ("NTRD_SHARE_IPOJURIS", "float", "非流通股(境内法人股:募集法人股)", "万股"),
    ("NTRD_SHARE_GENJURIS", "float", "非流通股(境内法人股:一般法人股)", "万股"),
    ("NTRD_SHARE_STRA_INVESTOR", "float", "非流通股(境内法人股:战略投资者持股)", "万股"),
    ("NTRD_SHARE_FUND", "float", "非流通股(境内法人股:基金持股)", "万股"),
    ("NTRD_SHARE_NAT", "float", "非流通股(自然人股)", "万股"),
    ("TRAN_SHARE", "float", "转配股", "万股"),
    ("FLOAT_SHARE_SENIOR", "float", "流通股(高管持股)", "万股"),
    ("SHARE_INEMP", "float", "内部职工股", "万股"),
    ("PREFERRED_SHARE", "float", "优先股", "万股"),
    ("NTRD_SHARE_NLIST_FRGN", "float", "非流通股(非上市外资股)", "万股"),
    ("STAQ_SHARE", "float", "STAQ 股", "万股"),
    ("NET_SHARE", "float", "NET 股", "万股"),
    ("SHARE_CHANGE_REASON", "string", "股本变动原因", ""),
    ("TOT_A_SHARE", "float", "A 股合计", "万股"),
    ("TOT_B_SHARE", "float", "B 股合计", "万股"),
    ("OTCA_SHARE", "float", "三板 A 股", "万股"),
    ("OTCB_SHARE", "float", "三板 B 股", "万股"),
    ("TOT_OTC_SHARE", "float", "三板合计", "万股"),
    ("SHARE_HK", "float", "香港上市股", "万股"),
    ("PRE_NON_TRADABLE_SHARE", "float", "股改前非流通股", "万股"),
    ("RESTRICTED_A_SHARE", "float", "限售 A 股", "万股"),
    ("RTD_A_SHARE_STATE", "float", "限售 A 股(国家持股)", "万股"),
    ("RTD_A_SHARE_STATEJUR", "float", "限售 A 股(国有法人持股)", "万股"),
    ("RTD_A_SHARE_OTHER_DOMES", "float", "限售 A 股(其他内资持股)", "万股"),
    ("RTD_A_SHARE_OTHER_DOMESJUR", "float", "限售 A 股(其他内资持股:境内法人持股)", "万股"),
    ("TOT_RESTRICTED_SHARE", "float", "限售股合计", "万股"),
]


def json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonical_field(raw_field: str, top_level_map: dict[str, str]) -> str:
    return top_level_map.get(raw_field, raw_field.lower())


def value_type(raw_field: str, source_type: str) -> str:
    if raw_field in STRING_FIELDS:
        return "string"
    if raw_field in ENUM_REFS:
        return "enum"
    if raw_field in DATE_FIELDS:
        return "date"
    type_l = source_type.strip().lower()
    if "int" in type_l:
        return "integer"
    if re.search(r"float|double|numeric|decimal", type_l):
        return "number"
    return "string"


def unit_info(dataset: str, data_type: str, raw_field: str, source_type: str, label: str, remark: str) -> tuple[str, int | float | None]:
    type_l = source_type.strip().lower()
    if raw_field in STRING_FIELDS or raw_field in ENUM_REFS:
        return "", None
    if not re.search(r"float|double|numeric|decimal|int", type_l):
        return "", None
    if dataset == "equity_structure" and re.search(r"float|double|numeric|decimal", type_l):
        return "万股", 10000

    text = f"{label} {remark}"
    unit = ""
    scale: int | float | None = None
    if raw_field in {"BASIC_EPS", "DILUTED_EPS", "EPS_BASIC", "NET_ASSET_PS", "INITIAL_NET_ASSET_PS"}:
        unit = "元/股"
    elif "万元" in text:
        unit, scale = "万元", 10000
    elif "万股" in text:
        unit, scale = "万股", 10000
    elif "元" in text:
        unit = "元"
    elif "%" in text or "％" in text or "率" in text:
        unit, scale = "%", 0.01
    elif "股" in text:
        unit = "股"

    if data_type == "balance_sheet" and raw_field == "TOT_SHARE":
        unit, scale = "股", None
    if unit == "" and data_type in {"balance_sheet", "income", "cashflow"} and re.search(
        r"float|double|numeric|decimal", type_l
    ):
        unit = "元"
    return unit, scale


def new_field_row(
    dataset: str,
    data_type: str,
    meta: dict[str, str],
    raw_field: str,
    source_type: str,
    label: str,
    remark: str,
    top_level_map: dict[str, str],
    source_path: str,
    review_status: str,
) -> dict[str, Any]:
    storage_location = "top_level" if raw_field in top_level_map else "data_json"
    is_metadata = raw_field in top_level_map
    unit, scale = unit_info(dataset, data_type, raw_field, source_type, label, remark)
    description = "" if remark.strip() == "-" else remark.strip()
    return {
        "contract_version": CONTRACT_VERSION,
        "source": SOURCE,
        "dataset": dataset,
        "data_type": data_type,
        "data_type_label_zh": meta["label"],
        "sdk_section": meta["sdk_section"],
        "sdk_function": meta["sdk_function"],
        "raw_field": raw_field,
        "canonical_field": canonical_field(raw_field, top_level_map),
        "label_zh": label.strip(),
        "description": description,
        "value_type": value_type(raw_field, source_type),
        "source_value_type": source_type.strip(),
        "unit": unit,
        "scale": scale,
        "enum_ref": ENUM_REFS.get(raw_field, ""),
        "storage_location": storage_location,
        "is_metadata": is_metadata,
        "is_core": raw_field in CORE_FIELDS.get(data_type, set()),
        "comp_type_scope": "all",
        "aliases": ALIASES.get(raw_field, []),
        "source_doc": f"AmazingData {meta['sdk_section']} {meta['sdk_function']}",
        "source_path": source_path,
        "review_status": review_status,
        "deprecated": False,
    }


FIELD_RE = re.compile(r"^\|\s*([A-Z][A-Z0-9_]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$")
TYPE_HEADER_RE = re.compile(r"^##\s+\d+\.\s+([a-z_]+)\s+-\s+(.+)$")


def read_table_fields(
    path: Path,
    project_root: Path,
    dataset: str,
    types: dict[str, dict[str, str]],
    top_level_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    data_type = ""
    source_path = path.relative_to(project_root).as_posix()

    for line in path.read_text(encoding="utf-8").splitlines():
        header = TYPE_HEADER_RE.match(line)
        if header:
            candidate = header.group(1)
            data_type = candidate if candidate in types else ""
            continue
        if not data_type:
            continue
        match = FIELD_RE.match(line)
        if not match:
            continue
        raw_field, source_type, label, remark = [part.strip() for part in match.groups()]
        if raw_field == "字段名":
            continue
        rows.append(
            new_field_row(
                dataset,
                data_type,
                types[data_type],
                raw_field,
                source_type,
                label,
                remark,
                top_level_map,
                source_path,
                "bootstrap_from_tables_description_checked_against_sdk_outline",
            )
        )
    return rows


def equity_rows() -> list[dict[str, Any]]:
    meta = {"label": "股本结构", "sdk_section": "3.5.6.3", "sdk_function": "get_equity_structure"}
    return [
        new_field_row(
            "equity_structure",
            "equity_structure",
            meta,
            raw_field,
            source_type,
            label,
            remark,
            TOP_LEVEL_EQUITY,
            "docs/third_party_sdk/AmazingData_development_guide.md",
            "manual_from_sdk_pdf_markdown_checked",
        )
        for raw_field, source_type, label, remark in EQUITY_RAW_FIELDS
    ]


def enum_rows() -> list[dict[str, Any]]:
    raw_rows = [
        ("REPORT_TYPE", "1", "3 月", "一季报报告期", 1, "AmazingData 4.1.8"),
        ("REPORT_TYPE", "2", "6 月", "半年报报告期", 2, "AmazingData 4.1.8"),
        ("REPORT_TYPE", "3", "9 月", "三季报报告期", 3, "AmazingData 4.1.8"),
        ("REPORT_TYPE", "4", "12 月", "年报报告期", 4, "AmazingData 4.1.8"),
        ("COMP_TYPE_CODE", "1", "非金融类", "非金融企业", 1, "AmazingData 财务字段备注"),
        ("COMP_TYPE_CODE", "2", "银行", "银行类企业", 2, "AmazingData 财务字段备注"),
        ("COMP_TYPE_CODE", "3", "保险", "保险类企业", 3, "AmazingData 财务字段备注"),
        ("COMP_TYPE_CODE", "4", "证券", "证券类企业", 4, "AmazingData 财务字段备注"),
        ("BOOLEAN_FLAG", "0", "否", "否/无效/非最新", 0, "AmazingData 字段备注"),
        ("BOOLEAN_FLAG", "1", "是", "是/有效/最新", 1, "AmazingData 字段备注"),
        ("DIV_PROGRESS", "1", "董事会预案", "公司董事会提出分红方案", 1, "AmazingData 4.1.10"),
        ("DIV_PROGRESS", "2", "股东大会通过", "股东大会审议通过", 2, "AmazingData 4.1.10"),
        ("DIV_PROGRESS", "3", "实施", "分红方案正式实施", 3, "AmazingData 4.1.10"),
        ("DIV_PROGRESS", "4", "未通过", "方案未通过", 4, "AmazingData 4.1.10"),
        ("DIV_PROGRESS", "12", "停止实施", "方案停止实施", 12, "AmazingData 4.1.10"),
        ("DIV_PROGRESS", "17", "股东提议", "股东提议", 17, "AmazingData 4.1.10"),
        ("DIV_PROGRESS", "19", "董事会预案预披露", "董事会预案预披露", 19, "AmazingData 4.1.10"),
        ("PROGRESS", "1", "董事会预案", "公司董事会提出配股方案", 1, "AmazingData 4.1.11"),
        ("PROGRESS", "2", "股东大会通过", "股东大会审议通过", 2, "AmazingData 4.1.11"),
        ("PROGRESS", "3", "实施", "配股方案正式实施", 3, "AmazingData 4.1.11"),
        ("PROGRESS", "4", "未通过", "方案未通过", 4, "AmazingData 4.1.11"),
        ("PROGRESS", "5", "证监会核准", "证监会审批通过", 5, "AmazingData 4.1.11"),
        ("PROGRESS", "6", "达成转让意向", "相关方达成意向", 6, "AmazingData 4.1.11"),
        ("PROGRESS", "7", "签署转让协议", "正式签署协议", 7, "AmazingData 4.1.11"),
        ("PROGRESS", "8", "国资委批准", "国资部门审批通过", 8, "AmazingData 4.1.11"),
        ("PROGRESS", "9", "商务部批准", "商务部审批通过", 9, "AmazingData 4.1.11"),
        ("PROGRESS", "10", "过户", "股权过户完成", 10, "AmazingData 4.1.11"),
        ("PROGRESS", "11", "延期实施", "方案延期执行", 11, "AmazingData 4.1.11"),
        ("PROGRESS", "12", "停止实施", "方案停止实施", 12, "AmazingData 4.1.11"),
        ("PROGRESS", "13", "分红方案待定", "方案待定", 13, "AmazingData 4.1.11"),
        ("PROGRESS", "14", "传闻", "市场传闻信息", 14, "AmazingData 4.1.11"),
        ("PROGRESS", "15", "证监会受理", "证监会受理", 15, "AmazingData 4.1.11"),
        ("PROGRESS", "16", "传闻被否认", "官方否认传闻", 16, "AmazingData 4.1.11"),
        ("PROGRESS", "17", "股东提议", "股东提出建议", 17, "AmazingData 4.1.11"),
        ("PROGRESS", "18", "保监会批复", "保监会审批通过", 18, "AmazingData 4.1.11"),
        ("PROGRESS", "19", "董事会预案预披露", "方案预披露", 19, "AmazingData 4.1.11"),
        ("PROGRESS", "20", "发审委通过", "发审委审核通过", 20, "AmazingData 4.1.11"),
        ("PROGRESS", "21", "发审委未通过", "发审委审核未通过", 21, "AmazingData 4.1.11"),
        ("PROGRESS", "22", "股东大会未通过", "股东大会否决", 22, "AmazingData 4.1.11"),
        ("PROGRESS", "23", "银监会批准", "银监会审批通过", 23, "AmazingData 4.1.11"),
        ("PROGRESS", "24", "证监会恢复审核", "证监会恢复审核", 24, "AmazingData 4.1.11"),
        ("PROGRESS", "25", "预发行", "预发行阶段", 25, "AmazingData 4.1.11"),
        ("PROGRESS", "26", "提交注册", "提交注册申请", 26, "AmazingData 4.1.11"),
        ("P_TYPECODE", "1", "不确定", "业绩预告类型", 1, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "2", "略减", "业绩预告类型", 2, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "3", "略增", "业绩预告类型", 3, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "4", "扭亏", "业绩预告类型", 4, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "5", "其他", "业绩预告类型", 5, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "6", "首亏", "业绩预告类型", 6, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "7", "续亏", "业绩预告类型", 7, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "8", "续盈", "业绩预告类型", 8, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "9", "预减", "业绩预告类型", 9, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "10", "预增", "业绩预告类型", 10, "AmazingData 3.5.5.5"),
        ("P_TYPECODE", "11", "持平", "业绩预告类型", 11, "AmazingData 3.5.5.5"),
    ]
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "source": SOURCE,
            "enum_name": enum_name,
            "code": code,
            "label_zh": label_zh,
            "description": description,
            "sort_order": sort_order,
            "source_doc": source_doc,
            "review_status": "checked_against_sdk_doc",
            "deprecated": False,
        }
        for enum_name, code, label_zh, description, sort_order, source_doc in raw_rows
    ]


def dataset_rows() -> list[dict[str, Any]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "source": SOURCE,
            "dataset": "financial_statement",
            "label_zh": "财务报表",
            "data_types": ["balance_sheet", "cashflow", "income", "profit_express", "profit_notice"],
            "storage_table": "financial_statement",
            "storage_tablespace": "warm_storage",
            "dictionary_tablespace": "pg_default",
            "source_doc": "AmazingData 3.5.5",
        },
        {
            "contract_version": CONTRACT_VERSION,
            "source": SOURCE,
            "dataset": "corporate_action",
            "label_zh": "公司行为",
            "data_types": ["dividend", "right_issue"],
            "storage_table": "corporate_action",
            "storage_tablespace": "warm_storage",
            "dictionary_tablespace": "pg_default",
            "source_doc": "AmazingData 3.5.7",
        },
        {
            "contract_version": CONTRACT_VERSION,
            "source": SOURCE,
            "dataset": "equity_structure",
            "label_zh": "股本结构",
            "data_types": ["equity_structure"],
            "storage_table": "equity_structure",
            "storage_tablespace": "warm_storage",
            "dictionary_tablespace": "pg_default",
            "source_doc": "AmazingData 3.5.6.3",
        },
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json_compact(row) for row in rows) + "\n", encoding="utf-8")


def generate(project_root: Path) -> None:
    project_root = project_root.resolve()
    out_dir = project_root / "scripts" / "field_dictionary" / "amazing_data"
    tables_dir = project_root / "docs" / "tables_description"
    out_dir.mkdir(parents=True, exist_ok=True)

    financial_rows = read_table_fields(
        tables_dir / "financial_statement.md",
        project_root,
        "financial_statement",
        FINANCIAL_TYPE_META,
        TOP_LEVEL_FINANCIAL,
    )
    corporate_rows = read_table_fields(
        tables_dir / "corporate_action.md",
        project_root,
        "corporate_action",
        CORPORATE_TYPE_META,
        TOP_LEVEL_CORPORATE,
    )
    equity = equity_rows()
    enums = enum_rows()
    datasets = dataset_rows()

    write_jsonl(out_dir / "financial_statement.fields.jsonl", financial_rows)
    write_jsonl(out_dir / "corporate_action.fields.jsonl", corporate_rows)
    write_jsonl(out_dir / "equity_structure.fields.jsonl", equity)
    write_jsonl(out_dir / "enums.jsonl", enums)
    (out_dir / "datasets.json").write_text(json.dumps(datasets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Generated field dictionary source files in {out_dir}")
    print(f"financial_statement fields: {len(financial_rows)}")
    print(f"corporate_action fields: {len(corporate_rows)}")
    print(f"equity_structure fields: {len(equity)}")
    print(f"enum values: {len(enums)}")
    print("Next: run regenerate_seed_sql.py to produce migrations/postgresql/security/0004_govern_seed.sql")


def main() -> None:
    parser = argparse.ArgumentParser()
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--project-root", type=Path, default=default_root)
    args = parser.parse_args()
    generate(args.project_root)


if __name__ == "__main__":
    main()

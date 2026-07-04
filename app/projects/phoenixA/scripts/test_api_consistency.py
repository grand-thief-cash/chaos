#!/usr/bin/env python3
"""
测试脚本：验证 PhoenixA API 文档与实际返回数据的一致性
"""

import json
import requests
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class APIStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass
class TestResult:
    """测试结果"""
    api_name: str
    endpoint: str
    status: APIStatus
    message: str
    diff: Optional[Dict[str, Any]] = None


class APITester:
    """API 测试器"""

    BASE_URL = "http://localhost:8085"

    def __init__(self):
        self.results: List[TestResult] = []

    def add_result(self, api_name: str, endpoint: str, status: APIStatus, message: str, diff: Optional[Dict] = None):
        """添加测试结果"""
        self.results.append(TestResult(api_name, endpoint, status, message, diff))
        print(f"[{status.value}] {api_name}: {message}")

    def test_securities(self):
        """测试 Securities API"""
        print("\n=== Testing Securities API ===")

        # Test 1: List securities
        try:
            resp = requests.get(f"{self.BASE_URL}/api/v2/securities?limit=1")
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                security = data["data"][0]
                expected_fields = ["security_id", "symbol", "asset_type", "market", "exchange", "name", "status", "created_at", "updated_at"]
                actual_fields = list(security.keys())
                missing = set(expected_fields) - set(actual_fields)
                extra = set(actual_fields) - set(expected_fields)

                if missing or extra:
                    self.add_result(
                        "Securities List",
                        "/api/v2/securities",
                        APIStatus.FAIL,
                        f"字段不匹配: 缺失={missing}, 多余={extra}",
                        {"expected": expected_fields, "actual": actual_fields, "missing": list(missing), "extra": list(extra)}
                    )
                else:
                    self.add_result("Securities List", "/api/v2/securities", APIStatus.PASS, "字段符合文档")
            else:
                self.add_result("Securities List", "/api/v2/securities", APIStatus.WARN, "响应格式异常")
        except Exception as e:
            self.add_result("Securities List", "/api/v2/securities", APIStatus.FAIL, str(e))

        # Test 2: Get single security by security_id (fetched from list)
        try:
            list_resp = requests.get(f"{self.BASE_URL}/api/v2/securities?limit=1")
            list_data = list_resp.json()
            rows = (list_data.get("data") or []) if isinstance(list_data, dict) else []
            if not rows or "security_id" not in rows[0]:
                self.add_result("Securities Get", "/api/v2/securities/{security_id}", APIStatus.WARN, "无法获取 security_id 用于测试")
            else:
                sid = rows[0]["security_id"]
                resp = requests.get(f"{self.BASE_URL}/api/v2/securities/{sid}")
                data = resp.json()
                if "data" in data:
                    self.add_result("Securities Get", "/api/v2/securities/{security_id}", APIStatus.PASS, "返回格式正确")
                else:
                    self.add_result("Securities Get", "/api/v2/securities/{security_id}", APIStatus.FAIL, "响应缺少 data 字段")
        except Exception as e:
            self.add_result("Securities Get", "/api/v2/securities/{security_id}", APIStatus.FAIL, str(e))

        # Test 3: Count securities
        try:
            resp = requests.get(f"{self.BASE_URL}/api/v2/securities/count")
            data = resp.json()
            if "data" in data and "count" in data["data"]:
                self.add_result("Securities Count", "/api/v2/securities/count", APIStatus.PASS, "返回格式正确")
            else:
                self.add_result("Securities Count", "/api/v2/securities/count", APIStatus.FAIL, "响应格式不符合预期")
        except Exception as e:
            self.add_result("Securities Count", "/api/v2/securities/count", APIStatus.FAIL, str(e))

    def test_bars(self):
        """测试 Bars API"""
        print("\n=== Testing Bars API ===")

        # Test 1: Query bars
        try:
            params = {
                "symbol": "000001",
                "start_date": "2024-01-01",
                "end_date": "2024-01-05",
                "period": "daily",
                "adjust": "nf",
                "limit": "1"
            }
            resp = requests.get(f"{self.BASE_URL}/api/v2/bars/stock/zh_a", params=params)
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                bar = data["data"][0]
                expected_fields = ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount", "preclose", "pct_chg"]
                actual_fields = list(bar.keys())
                missing = set(expected_fields) - set(actual_fields)
                extra = set(actual_fields) - set(expected_fields)

                if missing:
                    self.add_result(
                        "Bars Query",
                        "/api/v2/bars/{asset_type}/{market}",
                        APIStatus.FAIL,
                        f"缺少字段: {missing}",
                        {"expected": expected_fields, "actual": actual_fields, "missing": list(missing)}
                    )
                else:
                    self.add_result("Bars Query", "/api/v2/bars/{asset_type}/{market}", APIStatus.PASS, "字段符合文档")
            else:
                self.add_result("Bars Query", "/api/v2/bars/{asset_type}/{market}", APIStatus.WARN, "无数据返回")
        except Exception as e:
            self.add_result("Bars Query", "/api/v2/bars/{asset_type}/{market}", APIStatus.FAIL, str(e))

        # Test 2: Last update
        try:
            params = {"period": "daily", "adjust": "nf", "symbols": "000001"}
            resp = requests.get(f"{self.BASE_URL}/api/v2/bars/stock/zh_a/last_update", params=params)
            data = resp.json()
            if isinstance(data, dict) and "000001" in data:
                self.add_result("Bars Last Update", "/api/v2/bars/.../last_update", APIStatus.PASS, "返回格式正确")
            else:
                self.add_result("Bars Last Update", "/api/v2/bars/.../last_update", APIStatus.FAIL, "响应格式不符合预期")
        except Exception as e:
            self.add_result("Bars Last Update", "/api/v2/bars/.../last_update", APIStatus.FAIL, str(e))

    def test_taxonomy(self):
        """测试 Taxonomy API"""
        print("\n=== Testing Taxonomy API ===")

        # Test 1: by_security (Phase 2: path param is security_id, not symbol)
        try:
            sec_resp = requests.get(f"{self.BASE_URL}/api/v2/securities", params={"limit": "1"})
            sec_data = sec_resp.json() if sec_resp.status_code == 200 else {}
            sec_rows = sec_data.get("data") if isinstance(sec_data, dict) else sec_data
            _sec_id = (sec_rows or [{}])[0].get("security_id") if sec_rows else None
            if not _sec_id:
                self.add_result("Taxonomy by_security", "/api/v2/taxonomy/by_security/{security_id}", APIStatus.WARN, "无可用 security_id（security_registry 为空）")
            else:
                resp = requests.get(f"{self.BASE_URL}/api/v2/taxonomy/by_security/{_sec_id}")
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    # 预期字段（来自 TaxonomySecurityMapWithDetail，Phase 2 id-keyed）
                    expected_fields = [
                        "security_id", "category_id", "source", "taxonomy", "category_code", "category_name",
                        "level", "parent_code", "index_code",
                        "canonical_source", "canonical_taxonomy", "canonical_level",
                        "canonical_category_code", "canonical_category_name", "canonical_parent_code",
                        "canonical_index_code", "derived_flags",
                        "symbol", "asset_type", "market",
                        "created_at", "updated_at",
                    ]
                    actual_fields = list(item.keys())
                    missing = set(expected_fields) - set(actual_fields)

                    if missing:
                        self.add_result(
                            "Taxonomy by_security",
                            "/api/v2/taxonomy/by_security/{security_id}",
                            APIStatus.FAIL,
                            f"字段缺失: {missing}",
                            {
                                "expected": expected_fields,
                                "actual": actual_fields,
                                "missing": list(missing)
                            }
                        )
                    else:
                        self.add_result("Taxonomy by_security", "/api/v2/taxonomy/by_security/{security_id}", APIStatus.PASS, "字段符合文档")
                else:
                    self.add_result("Taxonomy by_security", "/api/v2/taxonomy/by_security/{security_id}", APIStatus.WARN, "无数据返回")
        except Exception as e:
            self.add_result("Taxonomy by_security", "/api/v2/taxonomy/by_security/{security_id}", APIStatus.FAIL, str(e))

        # Test 2: Categories - 响应格式检查
        try:
            resp = requests.get(f"{self.BASE_URL}/api/v2/taxonomy/amazing_data/swhy/zh_a/categories?limit=1")
            data = resp.json()
            # 实际返回格式: {"list": [...], "total": ...}
            if "list" in data and "total" in data:
                if isinstance(data["list"], list) and isinstance(data["total"], int):
                    self.add_result("Taxonomy Categories", "/api/v2/taxonomy/.../categories", APIStatus.PASS, "响应格式正确")
                else:
                    self.add_result(
                        "Taxonomy Categories",
                        "/api/v2/taxonomy/.../categories",
                        APIStatus.FAIL,
                        "响应格式错误",
                        {"expected": "{list: [...], total: number}", "actual": f"{type(data['list']).__name__}, {type(data['total']).__name__}"}
                    )
            else:
                self.add_result("Taxonomy Categories", "/api/v2/taxonomy/.../categories", APIStatus.FAIL, f"响应格式异常: {list(data.keys())}")
        except Exception as e:
            self.add_result("Taxonomy Categories", "/api/v2/taxonomy/.../categories", APIStatus.FAIL, str(e))

    def test_financial(self):
        """测试 Financial Statements API"""
        print("\n=== Testing Financial Statements API ===")

        try:
            params = {"security_id": "1", "limit": "1"}
            resp = requests.get(f"{self.BASE_URL}/api/v2/financial/amazing_data/balance_sheet", params=params)
            data = resp.json()
            # 返回格式: {"data": [...], "total": ...}
            if "data" in data and "total" in data:
                if len(data["data"]) > 0:
                    item = data["data"][0]
                    expected_main_fields = ["id", "security_id", "source", "statement_type", "reporting_period",
                                          "report_type", "statement_code", "security_name", "ann_date", "actual_ann_date",
                                          "comp_type_code", "data_json", "created_at", "updated_at"]
                    actual_fields = list(item.keys())
                    missing = set(expected_main_fields) - set(actual_fields)
                    if missing:
                        self.add_result(
                            "Financial Statements",
                            "/api/v2/financial/{source}/{statement_type}",
                            APIStatus.FAIL,
                            f"缺少主字段: {missing}",
                            {"expected": expected_main_fields, "actual": actual_fields, "missing": list(missing)}
                        )
                    else:
                        self.add_result("Financial Statements", "/api/v2/financial/{source}/{statement_type}", APIStatus.PASS, "响应格式正确")
            else:
                self.add_result("Financial Statements", "/api/v2/financial/{source}/{statement_type}", APIStatus.FAIL, "响应格式异常")
        except Exception as e:
            self.add_result("Financial Statements", "/api/v2/financial/{source}/{statement_type}", APIStatus.FAIL, str(e))

    def test_corporate_actions(self):
        """测试 Corporate Actions API"""
        print("\n=== Testing Corporate Actions API ===")

        try:
            params = {"security_id": "1", "limit": "1"}
            resp = requests.get(f"{self.BASE_URL}/api/v2/corporate-action/amazing_data/dividend", params=params)
            data = resp.json()
            # 返回格式: {"data": [...], "total": ...}
            if "data" in data and "total" in data:
                if len(data["data"]) > 0:
                    item = data["data"][0]
                    expected_main_fields = ["id", "security_id", "source", "action_type", "report_period",
                                          "ann_date", "progress_code", "data_json", "created_at", "updated_at"]
                    actual_fields = list(item.keys())
                    missing = set(expected_main_fields) - set(actual_fields)
                    if missing:
                        self.add_result(
                            "Corporate Actions",
                            "/api/v2/corporate-action/{source}/{action_type}",
                            APIStatus.FAIL,
                            f"缺少主字段: {missing}",
                            {"expected": expected_main_fields, "actual": actual_fields, "missing": list(missing)}
                        )
                    else:
                        self.add_result("Corporate Actions", "/api/v2/corporate-action/{source}/{action_type}", APIStatus.PASS, "响应格式正确")
            else:
                self.add_result("Corporate Actions", "/api/v2/corporate-action/{source}/{action_type}", APIStatus.FAIL, "响应格式异常")
        except Exception as e:
            self.add_result("Corporate Actions", "/api/v2/corporate-action/{source}/{action_type}", APIStatus.FAIL, str(e))

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("PhoenixA API 一致性测试")
        print("=" * 60)

        self.test_securities()
        self.test_bars()
        self.test_taxonomy()
        self.test_financial()
        self.test_corporate_actions()

        return self.generate_report()

    def generate_report(self) -> str:
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("测试报告")
        print("=" * 60)

        pass_count = sum(1 for r in self.results if r.status == APIStatus.PASS)
        fail_count = sum(1 for r in self.results if r.status == APIStatus.FAIL)
        warn_count = sum(1 for r in self.results if r.status == APIStatus.WARN)

        print(f"\n总计: {len(self.results)} | 通过: {pass_count} | 失败: {fail_count} | 警告: {warn_count}")

        if fail_count > 0 or warn_count > 0:
            print("\n需要关注的差异:")

            for result in self.results:
                if result.status in [APIStatus.FAIL, APIStatus.WARN]:
                    print(f"\n[{result.status.value}] {result.api_name} ({result.endpoint})")
                    print(f"  {result.message}")
                    if result.diff:
                        print(f"  详情:")
                        for key, value in result.diff.items():
                            print(f"    {key}: {value}")

        # 生成 JSON 格式的 diff 报告
        diff_report = {
            "summary": {
                "total": len(self.results),
                "pass": pass_count,
                "fail": fail_count,
                "warn": warn_count
            },
            "differences": []
        }

        for result in self.results:
            if result.status in [APIStatus.FAIL, APIStatus.WARN]:
                diff_report["differences"].append({
                    "api": result.api_name,
                    "endpoint": result.endpoint,
                    "status": result.status.value,
                    "message": result.message,
                    "diff": result.diff
                })

        return json.dumps(diff_report, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    tester = APITester()
    report = tester.run_all_tests()

    # 保存报告到文件
    report_file = "/home/machine/projects/chaos/app/projects/phoenixA/docs/api_diff_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n详细报告已保存到: {report_file}")

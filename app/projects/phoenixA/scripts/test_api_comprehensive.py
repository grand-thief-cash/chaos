#!/usr/bin/env python3
"""
PhoenixA API 全面测试脚本
验证 API 返回数据与文档描述的一致性
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

# API 基础配置
BASE_URL = "http://localhost:8085"
TIMEOUT = 30


class TestStatus(Enum):
    """测试状态"""
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


@dataclass
class FieldCheckResult:
    """字段检查结果"""
    field_name: str
    status: TestStatus
    expected_type: str
    actual_type: Optional[str] = None
    message: str = ""
    found_in_response: bool = False


@dataclass
class APITestResult:
    """API 测试结果"""
    api_name: str
    endpoint: str
    status: TestStatus
    response_code: int
    message: str = ""
    field_checks: List[FieldCheckResult] = field(default_factory=list)
    response_sample: Dict = field(default_factory=dict)
    extra_fields: Set[str] = field(default_factory=set)
    missing_fields: Set[str] = field(default_factory=set)


class PhoenixAAPITester:
    """PhoenixA API 测试器"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[APITestResult] = []
        self.session = requests.Session()

    def _make_request(self, endpoint: str, params: Dict = None) -> requests.Response:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=TIMEOUT)
            return response
        except Exception as e:
            raise Exception(f"请求失败: {url}, 错误: {str(e)}")

    def _get_first_security_id(self) -> Optional[int]:
        """Fetch the first security_id from /api/v2/securities (Phase 2 id-based routes)."""
        try:
            resp = self._make_request("/api/v2/securities/", {"market": "zh_a", "page_size": 1})
            if resp.status_code == 200:
                data = resp.json()
                rows = data if isinstance(data, list) else (data.get("data") or data.get("list") or [])
                for row in rows:
                    sid = row.get("security_id") or row.get("id")
                    if sid:
                        return int(sid)
        except Exception:
            pass
        return None

    def _get_first_category_id(self, source: str = "amazing_data", taxonomy: str = "sw_l1", market: str = "zh_a") -> Optional[int]:
        """Fetch the first taxonomy_category id from the categories list (Phase 2 id-based routes)."""
        try:
            resp = self._make_request(f"/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories", {"page_size": 1})
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("list") if isinstance(data, dict) else data
                for row in rows or []:
                    cid = row.get("id")
                    if cid:
                        return int(cid)
        except Exception:
            pass
        return None

    def _get_type_name(self, value: Any) -> str:
        """获取值的类型名称"""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "float64"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, dict):
            return "object"
        elif isinstance(value, list):
            return "array"
        else:
            return type(value).__name__

    def _check_field(
        self,
        response_data: Dict,
        field_name: str,
        expected_type: str,
        required: bool = True
    ) -> FieldCheckResult:
        """检查字段是否存在和类型是否正确"""
        result = FieldCheckResult(
            field_name=field_name,
            expected_type=expected_type,
            status=TestStatus.PASSED
        )

        if field_name not in response_data:
            result.found_in_response = False
            if required:
                result.status = TestStatus.FAILED
                result.message = f"字段缺失: {field_name}"
            else:
                result.status = TestStatus.WARNING
                result.message = f"可选字段不存在: {field_name}"
            return result

        result.found_in_response = True
        actual_value = response_data[field_name]
        result.actual_type = self._get_type_name(actual_value)

        # 类型检查（允许 null）
        if actual_value is None:
            result.status = TestStatus.WARNING
            result.message = f"字段值为 null: {field_name}"
        elif expected_type != "any" and result.actual_type != expected_type:
            # 允许一些类型兼容性
            type_compatible = False

            # float64 和 integer 可以兼容
            if expected_type == "float64" and result.actual_type == "integer":
                type_compatible = True
            # 允许 integer 和 float64 互换
            elif expected_type == "integer" and result.actual_type == "float64":
                type_compatible = True
            # 允许 "object" 和 "object" 严格匹配
            elif expected_type == "object" and result.actual_type == "object":
                type_compatible = True
            elif expected_type == "array" and result.actual_type == "array":
                type_compatible = True

            if not type_compatible:
                result.status = TestStatus.FAILED
                result.message = f"类型不匹配: 期望 {expected_type}, 实际 {result.actual_type}"
            else:
                result.status = TestStatus.WARNING
                result.message = f"类型兼容但不同: 期望 {expected_type}, 实际 {result.actual_type}"

        return result

    def _check_fields(
        self,
        response_data: Dict,
        expected_fields: Dict[str, str],
        extra_allowed: bool = True
    ) -> List[FieldCheckResult]:
        """批量检查字段"""
        results = []
        missing_fields = []

        # 检查期望字段
        for field_name, expected_type in expected_fields.items():
            result = self._check_field(response_data, field_name, expected_type)
            results.append(result)
            if not result.found_in_response and result.status == TestStatus.FAILED:
                missing_fields.append(field_name)

        # 检查多余字段
        if extra_allowed:
            expected_keys = set(expected_fields.keys())
            actual_keys = set(response_data.keys())
            extra_fields = actual_keys - expected_keys
            if extra_fields:
                for extra_field in extra_fields:
                    results.append(FieldCheckResult(
                        field_name=extra_field,
                        status=TestStatus.WARNING,
                        expected_type="unknown",
                        actual_type=self._get_type_name(response_data[extra_field]),
                        found_in_response=True,
                        message=f"文档中未列出的字段: {extra_field}"
                    ))

        return results

    def test_securities_list(self) -> APITestResult:
        """测试证券列表 API"""
        endpoint = "/api/v2/securities"
        result = APITestResult(
            api_name="Securities - 列表",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            # 检查响应结构
            if "data" not in data or not isinstance(data["data"], list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 缺少 data 字段或不是数组"
                return result

            if "total" not in data:
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 缺少 total 字段"
                return result

            # 检查第一个证券对象的字段
            if len(data["data"]) > 0:
                first_security = data["data"][0]

                expected_fields = {
                    "security_id": "integer",
                    "symbol": "string",
                    "asset_type": "string",
                    "market": "string",
                    "exchange": "string",
                    "name": "string",
                    "full_name": "string",
                    "status": "string",
                    "list_date": "string",
                    "delist_date": "string",
                    "created_at": "string",
                    "updated_at": "string",
                }

                result.field_checks = self._check_fields(first_security, expected_fields)

                # 统计失败和警告
                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data['data'])} 条证券数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有证券数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_securities_detail(self) -> APITestResult:
        """测试单个证券详情 API"""
        # 路径参数已从 symbol 迁移到 security_id，先从列表取一个真实 id
        try:
            _list_resp = self._make_request("/api/v2/securities", {"limit": "1"})
            _list_data = _list_resp.json() if _list_resp.status_code == 200 else {}
            _rows = (_list_data.get("data") or []) if isinstance(_list_data, dict) else []
            _sid = str(_rows[0].get("security_id", "1")) if _rows else "1"
        except Exception:
            _sid = "1"
        endpoint = f"/api/v2/securities/{_sid}"
        result = APITestResult(
            api_name="Securities - 详情",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if "data" not in data:
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 缺少 data 字段"
                return result

            security = data["data"]

            expected_fields = {
                "security_id": "integer",
                "symbol": "string",
                "asset_type": "string",
                "market": "string",
                "exchange": "string",
                "name": "string",
                "full_name": "string",
                "status": "string",
                "list_date": "string",
                "delist_date": "string",
                "created_at": "string",
                "updated_at": "string",
            }

            result.field_checks = self._check_fields(security, expected_fields)

            failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
            if failed:
                result.status = TestStatus.FAILED
                result.message = f"字段检查失败: {len(failed)} 个"
            else:
                result.message = f"成功获取证券详情: {security.get('name', 'N/A')}"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_securities_count(self) -> APITestResult:
        """测试证券计数 API"""
        endpoint = "/api/v2/securities/count"
        result = APITestResult(
            api_name="Securities - 计数",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if "count" not in data:
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 缺少 count 字段"
                return result

            expected_fields = {
                "count": "integer",
            }

            result.field_checks = self._check_fields(data, expected_fields)

            failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
            if failed:
                result.status = TestStatus.FAILED
                result.message = f"字段检查失败: {len(failed)} 个"
            else:
                result.message = f"证券总数: {data['count']}"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_bars_data(self) -> APITestResult:
        """测试 K 线数据 API"""
        endpoint = "/api/v2/bars/stock/zh_a"
        params = {
            "symbol": "000001",
            "start_date": "2024-05-01",
            "end_date": "2024-05-15",
            "period": "daily",
            "adjust": "nf",
            "limit": 10
        }
        result = APITestResult(
            api_name="Bars - K线数据",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是数组"
                return result

            if len(data) > 0:
                first_bar = data[0]

                # 基础字段
                expected_fields = {
                    "symbol": "string",
                    "trade_date": "string",
                    "open": "float64",
                    "high": "float64",
                    "low": "float64",
                    "close": "float64",
                    "volume": "integer",
                    "amount": "integer",
                    "preclose": "float64",
                    "pct_chg": "float64",
                }

                result.field_checks = self._check_fields(first_bar, expected_fields)

                # 检查 Baostock 扩展字段（可选）
                baostock_fields = [
                    "turn", "pe_ttm", "ps_ttm", "pb_mrq", "pcf_ncf_ttm"
                ]
                for field in baostock_fields:
                    if field in first_bar:
                        result.field_checks.append(FieldCheckResult(
                            field_name=field,
                            status=TestStatus.WARNING,
                            expected_type="float64",
                            actual_type=self._get_type_name(first_bar[field]),
                            found_in_response=True,
                            message=f"Baostock 扩展字段存在: {field}"
                        ))

                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data)} 条 K 线数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有 K 线数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_bars_last_update(self) -> APITestResult:
        """测试 K 线最新日期 API"""
        endpoint = "/api/v2/bars/stock/zh_a/last_update"
        params = {
            "period": "daily",
            "adjust": "nf",
            "symbols": "000001,600000"
        }
        result = APITestResult(
            api_name="Bars - 最新日期",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, dict):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是对象"
                return result

            result.message = f"最新日期数据: {len(data)} 个证券"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_financial_balance_sheet(self) -> APITestResult:
        """测试资产负债表 API"""
        endpoint = "/api/v2/financial/amazing_data/balance_sheet"
        params = {
            "symbols": "000001",
            "limit": 1
        }
        result = APITestResult(
            api_name="Financial - 资产负债表",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list) or len(data) == 0:
                result.status = TestStatus.WARNING
                result.message = "没有资产负债表数据"
                self.results.append(result)
                return result

            first_item = data[0]

            # 检查外层字段
            outer_expected_fields = {
                "id": "integer",
                "source": "string",
                "symbol": "string",
                "market": "string",
                "statement_type": "string",
                "report_period": "string",
                "report_type": "string",
                "statement_code": "string",
                "security_name": "string",
                "ann_date": "string",
                "actual_ann_date": "string",
                "comp_type_code": "integer",
                "data_json": "object",
                "created_at": "string",
                "updated_at": "string",
            }

            result.field_checks = self._check_fields(first_item, outer_expected_fields)

            # 检查 data_json 字段
            if "data_json" in first_item and isinstance(first_item["data_json"], dict):
                data_json = first_item["data_json"]

                # 检查一些关键字段
                key_data_json_fields = {
                    "MARKET_CODE": "string",
                    "SECURITY_NAME": "string",
                    "STATEMENT_TYPE": "string",
                    "REPORT_TYPE": "string",
                    "REPORTING_PERIOD": "string",
                    "ANN_DATE": "string",
                    "TOTAL_ASSETS": "float64",
                    "TOTAL_LIAB": "float64",
                    "TOT_LIAB_SHARE_EQUITY": "float64",
                    "TOT_SHARE": "float64",
                    "CURRENCY_CAP": "float64",
                }

                for field, expected_type in key_data_json_fields.items():
                    check = self._check_field(data_json, field, expected_type, required=False)
                    result.field_checks.append(check)

            failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
            if failed:
                result.status = TestStatus.FAILED
                result.message = f"字段检查失败: {len(failed)} 个"
            else:
                result.message = f"成功获取 {len(data)} 条资产负债表数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_financial_income(self) -> APITestResult:
        """测试利润表 API"""
        endpoint = "/api/v2/financial/amazing_data/income"
        params = {
            "symbols": "000001",
            "limit": 1
        }
        result = APITestResult(
            api_name="Financial - 利润表",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list) or len(data) == 0:
                result.status = TestStatus.WARNING
                result.message = "没有利润表数据"
                self.results.append(result)
                return result

            first_item = data[0]

            outer_expected_fields = {
                "id": "integer",
                "source": "string",
                "symbol": "string",
                "market": "string",
                "statement_type": "string",
                "report_period": "string",
                "report_type": "string",
                "statement_code": "string",
                "security_name": "string",
                "ann_date": "string",
                "actual_ann_date": "string",
                "comp_type_code": "integer",
                "data_json": "object",
                "created_at": "string",
                "updated_at": "string",
            }

            result.field_checks = self._check_fields(first_item, outer_expected_fields)

            if "data_json" in first_item and isinstance(first_item["data_json"], dict):
                data_json = first_item["data_json"]

                key_data_json_fields = {
                    "MARKET_CODE": "string",
                    "SECURITY_NAME": "string",
                    "STATEMENT_TYPE": "string",
                    "REPORT_TYPE": "string",
                    "REPORTING_PERIOD": "string",
                    "ANN_DATE": "string",
                    "TOT_OPERA_REV": "float64",
                    "TOT_OPERA_COST": "float64",
                    "OPERA_PROFIT": "float64",
                    "TOTAL_PROFIT": "float64",
                    "NET_PRO_INCL_MIN_INT_INC": "float64",
                    "NET_PRO_EXCL_MIN_INT_INC": "float64",
                    "BASIC_EPS": "float64",
                }

                for field, expected_type in key_data_json_fields.items():
                    check = self._check_field(data_json, field, expected_type, required=False)
                    result.field_checks.append(check)

            failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
            if failed:
                result.status = TestStatus.FAILED
                result.message = f"字段检查失败: {len(failed)} 个"
            else:
                result.message = f"成功获取 {len(data)} 条利润表数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_corporate_action_dividend(self) -> APITestResult:
        """测试分红数据 API"""
        endpoint = "/api/v2/corporate-action/amazing_data/dividend"
        params = {
            "symbols": "000001",
            "limit": 1
        }
        result = APITestResult(
            api_name="Corporate Action - 分红",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list) or len(data) == 0:
                result.status = TestStatus.WARNING
                result.message = "没有分红数据"
                self.results.append(result)
                return result

            first_item = data[0]

            outer_expected_fields = {
                "id": "integer",
                "source": "string",
                "symbol": "string",
                "market": "string",
                "action_type": "string",
                "report_period": "string",
                "ann_date": "string",
                "progress_code": "string",
                "data_json": "object",
                "created_at": "string",
                "updated_at": "string",
            }

            result.field_checks = self._check_fields(first_item, outer_expected_fields)

            if "data_json" in first_item and isinstance(first_item["data_json"], dict):
                data_json = first_item["data_json"]

                key_data_json_fields = {
                    "MARKET_CODE": "string",
                    "DIV_PROGRESS": "string",
                    "DVD_PER_SHARE_STK": "float64",
                    "DVD_PER_SHARE_PRE_TAX_CASH": "float64",
                    "DVD_PER_SHARE_AFTER_TAX_CASH": "float64",
                    "DATE_EQY_RECORD": "string",
                    "DATE_EX": "string",
                    "DATE_DVD_PAYOUT": "string",
                    "ANN_DATE": "string",
                    "REPORT_PERIOD": "string",
                }

                for field, expected_type in key_data_json_fields.items():
                    check = self._check_field(data_json, field, expected_type, required=False)
                    result.field_checks.append(check)

            failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
            if failed:
                result.status = TestStatus.FAILED
                result.message = f"字段检查失败: {len(failed)} 个"
            else:
                result.message = f"成功获取 {len(data)} 条分红数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_taxonomy_by_security(self) -> APITestResult:
        """测试证券分类映射 API"""
        security_id = self._get_first_security_id()
        endpoint = f"/api/v2/taxonomy/by_security/{security_id}" if security_id else "/api/v2/taxonomy/by_security/{security_id}"
        result = APITestResult(
            api_name="Taxonomy - 证券分类映射",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        if security_id is None:
            result.status = TestStatus.SKIPPED
            result.message = "无可用 security_id（security_registry 为空），跳过"
            self.results.append(result)
            return result

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是数组"
                return result

            if len(data) > 0:
                first_item = data[0]

                expected_fields = {
                    "security_id": "integer",
                    "category_id": "integer",
                    "source": "string",
                    "taxonomy": "string",
                    "category_code": "string",
                    "category_name": "string",
                    "level": "integer",
                    "parent_code": "string",
                    "index_code": "string",
                    "canonical_source": "string",
                    "canonical_taxonomy": "string",
                    "canonical_level": "integer",
                    "canonical_category_code": "string",
                    "canonical_category_name": "string",
                    "canonical_parent_code": "string",
                    "canonical_index_code": "string",
                    "derived_flags": "object",
                    "symbol": "string",
                    "asset_type": "string",
                    "market": "string",
                    "created_at": "string",
                    "updated_at": "string",
                }

                result.field_checks = self._check_fields(first_item, expected_fields)

                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data)} 条分类映射数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有分类映射数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_taxonomy_categories(self) -> APITestResult:
        """测试分类列表 API"""
        endpoint = "/api/v2/taxonomy/amazing_data/sw_l1/zh_a/categories"
        result = APITestResult(
            api_name="Taxonomy - 分类列表",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是数组"
                return result

            if len(data) > 0:
                first_item = data[0]

                expected_fields = {
                    "id": "integer",
                    "source": "string",
                    "taxonomy": "string",
                    "market": "string",
                    "code": "string",
                    "name": "string",
                    "level": "integer",
                    "parent_code": "string",
                    "is_leaf": "boolean",
                    "index_code": "string",
                    "created_at": "string",
                    "updated_at": "string",
                }

                result.field_checks = self._check_fields(first_item, expected_fields)

                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data)} 条分类数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有分类数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_taxonomy_industry_constituents(self) -> APITestResult:
        """测试行业成分股 API"""
        category_id = self._get_first_category_id()
        endpoint = f"/api/v2/taxonomy/amazing_data/sw_l1/zh_a/industry-constituents/by_category/{category_id}" if category_id else "/api/v2/taxonomy/amazing_data/sw_l1/zh_a/industry-constituents/by_category/{category_id}"
        result = APITestResult(
            api_name="Taxonomy - 行业成分股",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        if category_id is None:
            result.status = TestStatus.SKIPPED
            result.message = "无可用 category_id（taxonomy_category 为空），跳过"
            self.results.append(result)
            return result

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是数组"
                return result

            if len(data) > 0:
                first_item = data[0]

                expected_fields = {
                    "id": "integer",
                    "category_id": "integer",
                    "security_id": "integer",
                    "in_date": "string",
                    "out_date": "string",
                    "created_at": "string",
                    "updated_at": "string",
                }

                result.field_checks = self._check_fields(first_item, expected_fields)

                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data)} 条成分股数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有成分股数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_taxonomy_industry_weights(self) -> APITestResult:
        """测试行业权重 API"""
        category_id = self._get_first_category_id()
        endpoint = f"/api/v2/taxonomy/amazing_data/sw_l1/zh_a/industry-weights/{category_id}" if category_id else "/api/v2/taxonomy/amazing_data/sw_l1/zh_a/industry-weights/{category_id}"
        result = APITestResult(
            api_name="Taxonomy - 行业权重",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        if category_id is None:
            result.status = TestStatus.SKIPPED
            result.message = "无可用 category_id（taxonomy_category 为空），跳过"
            self.results.append(result)
            return result

        try:
            # trade_date is required; use a recent date (data may be empty → WARNING).
            response = self._make_request(endpoint, {"trade_date": "2026-06-30"})
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是数组"
                return result

            if len(data) > 0:
                first_item = data[0]

                expected_fields = {
                    "category_id": "integer",
                    "security_id": "integer",
                    "trade_date": "string",
                    "weight": "float64",
                    "created_at": "string",
                    "updated_at": "string",
                }

                result.field_checks = self._check_fields(first_item, expected_fields)

                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data)} 条权重数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有权重数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_taxonomy_industry_daily(self) -> APITestResult:
        """测试行业日行情 API"""
        category_id = self._get_first_category_id()
        endpoint = "/api/v2/taxonomy/amazing_data/sw_l1/zh_a/industry-daily"
        params = {
            "category_id": category_id,
            "start_date": "2024-05-01",
            "end_date": "2026-06-30",
            "limit": 5,
        }
        result = APITestResult(
            api_name="Taxonomy - 行业日行情",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        if category_id is None:
            result.status = TestStatus.SKIPPED
            result.message = "无可用 category_id（taxonomy_category 为空），跳过"
            self.results.append(result)
            return result

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是数组"
                return result

            if len(data) > 0:
                first_item = data[0]

                expected_fields = {
                    "category_id": "integer",
                    "trade_date": "string",
                    "open": "float64",
                    "high": "float64",
                    "low": "float64",
                    "close": "float64",
                    "pre_close": "float64",
                    "amount": "float64",
                    "volume": "float64",
                    "pb": "float64",
                    "pe": "float64",
                    "total_cap": "float64",
                    "a_float_cap": "float64",
                    "created_at": "string",
                    "updated_at": "string",
                }

                result.field_checks = self._check_fields(first_item, expected_fields)

                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data)} 条行业日行情数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有行业日行情数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_securities_list_filter(self) -> APITestResult:
        """测试证券列表过滤 API"""
        endpoint = "/api/v2/securities"
        params = {
            "symbols": "000001,600000",
            "limit": 10
        }
        result = APITestResult(
            api_name="Securities - 列表过滤",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if "data" not in data or not isinstance(data["data"], list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 缺少 data 字段或不是数组"
                return result

            if "total" not in data:
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 缺少 total 字段"
                return result

            result.message = f"成功获取 {len(data['data'])} 条证券数据 (total={data.get('total', 0)})"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_financial_cashflow(self) -> APITestResult:
        """测试现金流量表 API"""
        endpoint = "/api/v2/financial/amazing_data/cashflow"
        params = {
            "symbols": "000001",
            "limit": 1
        }
        result = APITestResult(
            api_name="Financial - 现金流量表",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list) or len(data) == 0:
                result.status = TestStatus.WARNING
                result.message = "没有现金流量表数据"
                self.results.append(result)
                return result

            first_item = data[0]

            outer_expected_fields = {
                "id": "integer",
                "source": "string",
                "symbol": "string",
                "market": "string",
                "statement_type": "string",
                "report_period": "string",
                "report_type": "string",
                "statement_code": "string",
                "security_name": "string",
                "ann_date": "string",
                "actual_ann_date": "string",
                "comp_type_code": "integer",
                "data_json": "object",
                "created_at": "string",
                "updated_at": "string",
            }

            result.field_checks = self._check_fields(first_item, outer_expected_fields)

            if "data_json" in first_item and isinstance(first_item["data_json"], dict):
                data_json = first_item["data_json"]

                key_data_json_fields = {
                    "MARKET_CODE": "string",
                    "SECURITY_NAME": "string",
                    "STATEMENT_TYPE": "string",
                    "REPORT_TYPE": "string",
                    "REPORTING_PERIOD": "string",
                    "ANN_DATE": "string",
                    "NET_CASH_FLOW_OPERA_ACT": "float64",
                    "NET_CASH_FLOW_INV_ACT": "float64",
                    "NET_CASH_FLOW_FIN_ACT": "float64",
                }

                for field, expected_type in key_data_json_fields.items():
                    check = self._check_field(data_json, field, expected_type, required=False)
                    result.field_checks.append(check)

            failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
            if failed:
                result.status = TestStatus.FAILED
                result.message = f"字段检查失败: {len(failed)} 个"
            else:
                result.message = f"成功获取 {len(data)} 条现金流量表数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_taxonomy_category_detail(self) -> APITestResult:
        """测试分类详情 API"""
        endpoint = "/api/v2/taxonomy/amazing_data/sw_l1/zh_a/categories/801010"
        result = APITestResult(
            api_name="Taxonomy - 分类详情",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, dict):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是对象"
                return result

            expected_fields = {
                "id": "integer",
                "source": "string",
                "taxonomy": "string",
                "market": "string",
                "code": "string",
                "name": "string",
                "level": "integer",
                "parent_code": "string",
                "is_leaf": "boolean",
                "index_code": "string",
                "created_at": "string",
                "updated_at": "string",
            }

            result.field_checks = self._check_fields(data, expected_fields)

            failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
            if failed:
                result.status = TestStatus.FAILED
                result.message = f"字段检查失败: {len(failed)} 个"
            else:
                result.message = f"成功获取分类详情: {data.get('name', 'N/A')}"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_taxonomy_constituents_by_stock(self) -> APITestResult:
        """测试按股票查询成分股 API"""
        security_id = self._get_first_security_id()
        endpoint = f"/api/v2/taxonomy/amazing_data/sw_l1/zh_a/industry-constituents/by_security/{security_id}" if security_id else "/api/v2/taxonomy/amazing_data/sw_l1/zh_a/industry-constituents/by_security/{security_id}"
        result = APITestResult(
            api_name="Taxonomy - 按股票查询成分股",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        if security_id is None:
            result.status = TestStatus.SKIPPED
            result.message = "无可用 security_id（security_registry 为空），跳过"
            self.results.append(result)
            return result

        try:
            response = self._make_request(endpoint)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list):
                result.status = TestStatus.FAILED
                result.message = f"响应格式错误: 不是数组"
                return result

            if len(data) > 0:
                first_item = data[0]

                expected_fields = {
                    "id": "integer",
                    "category_id": "integer",
                    "security_id": "integer",
                    "in_date": "string",
                    "out_date": "string",
                    "created_at": "string",
                    "updated_at": "string",
                }

                result.field_checks = self._check_fields(first_item, expected_fields)

                failed = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                if failed:
                    result.status = TestStatus.FAILED
                    result.message = f"字段检查失败: {len(failed)} 个"
                else:
                    result.message = f"成功获取 {len(data)} 条成分股数据"
            else:
                result.status = TestStatus.WARNING
                result.message = "没有成分股数据"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def test_bars_fields_param(self) -> APITestResult:
        """测试 K 线数据 fields 参数"""
        endpoint = "/api/v2/bars/stock/zh_a"
        params = {
            "symbol": "000001",
            "start_date": "2024-05-01",
            "end_date": "2024-05-15",
            "period": "daily",
            "adjust": "nf",
            "fields": "symbol,trade_date,open,high,low,close",
            "limit": 5
        }
        result = APITestResult(
            api_name="Bars - fields参数测试",
            endpoint=endpoint,
            status=TestStatus.PASSED,
            response_code=0
        )

        try:
            response = self._make_request(endpoint, params)
            result.response_code = response.status_code

            if response.status_code != 200:
                result.status = TestStatus.FAILED
                result.message = f"HTTP 错误: {response.status_code}"
                return result

            data = response.json()
            result.response_sample = data

            if not isinstance(data, list) or len(data) == 0:
                result.status = TestStatus.WARNING
                result.message = "没有 K 线数据"
                self.results.append(result)
                return result

            first_bar = data[0]

            # 验证只返回了请求的字段
            expected_fields = {
                "symbol": "string",
                "trade_date": "string",
                "open": "float64",
                "high": "float64",
                "low": "float64",
                "close": "float64",
            }

            result.field_checks = self._check_fields(first_bar, expected_fields)

            # 检查是否有额外字段
            extra_fields = set(first_bar.keys()) - set(expected_fields.keys())
            if extra_fields:
                result.status = TestStatus.FAILED
                result.message = f"fields参数未生效，返回了额外字段: {extra_fields}"
            else:
                result.message = f"fields参数生效，只返回了 {len(expected_fields)} 个字段"

        except Exception as e:
            result.status = TestStatus.FAILED
            result.message = f"测试异常: {str(e)}"

        self.results.append(result)
        return result

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 80)
        print("PhoenixA API 全面测试")
        print(f"测试目标: {self.base_url}")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()

        # Securities API 测试
        print("1. Securities API 测试")
        print("-" * 80)
        self.test_securities_list()
        self.test_securities_list_filter()
        self.test_securities_detail()
        self.test_securities_count()
        print()

        # Bars API 测试
        print("2. Bars API 测试")
        print("-" * 80)
        self.test_bars_data()
        self.test_bars_last_update()
        self.test_bars_fields_param()
        print()

        # Financial Statements API 测试
        print("3. Financial Statements API 测试")
        print("-" * 80)
        self.test_financial_balance_sheet()
        self.test_financial_income()
        self.test_financial_cashflow()
        print()

        # Corporate Actions API 测试
        print("4. Corporate Actions API 测试")
        print("-" * 80)
        self.test_corporate_action_dividend()
        print()

        # Taxonomy API 测试
        print("5. Taxonomy API 测试")
        print("-" * 80)
        self.test_taxonomy_by_security()
        self.test_taxonomy_categories()
        self.test_taxonomy_category_detail()
        self.test_taxonomy_industry_constituents()
        self.test_taxonomy_constituents_by_stock()
        self.test_taxonomy_industry_weights()
        self.test_taxonomy_industry_daily()
        print()

    def print_summary(self):
        """打印测试摘要"""
        print("=" * 80)
        print("测试摘要")
        print("=" * 80)

        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in self.results if r.status == TestStatus.WARNING)
        total = len(self.results)

        print(f"总计: {total} 个测试")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"警告: {warnings}")
        print()

        # 打印详细结果
        for i, result in enumerate(self.results, 1):
            status_icon = {
                TestStatus.PASSED: "✓",
                TestStatus.FAILED: "✗",
                TestStatus.WARNING: "⚠",
                TestStatus.SKIPPED: "⊘"
            }[result.status]

            print(f"{i}. [{status_icon}] {result.api_name}")
            print(f"   端点: {result.endpoint}")
            print(f"   状态码: {result.response_code}")
            print(f"   结果: {result.status.value}")
            print(f"   消息: {result.message}")

            if result.field_checks:
                failed_checks = [f for f in result.field_checks if f.status == TestStatus.FAILED]
                warning_checks = [f for f in result.field_checks if f.status == TestStatus.WARNING]
                extra_checks = [f for f in result.field_checks if "文档中未列出" in f.message]

                if failed_checks:
                    print(f"   失败字段 ({len(failed_checks)}):")
                    for fc in failed_checks[:5]:  # 只显示前5个
                        print(f"     - {fc.field_name}: {fc.message}")
                    if len(failed_checks) > 5:
                        print(f"     ... 还有 {len(failed_checks) - 5} 个失败字段")

                if warning_checks:
                    print(f"   警告字段 ({len(warning_checks)}):")
                    for wc in warning_checks[:3]:
                        print(f"     - {wc.field_name}: {wc.message}")
                    if len(warning_checks) > 3:
                        print(f"     ... 还有 {len(warning_checks) - 3} 个警告字段")

                if extra_checks:
                    print(f"   额外字段 ({len(extra_checks)}):")
                    for ec in extra_checks[:5]:
                        print(f"     - {ec.field_name} ({ec.actual_type})")
                    if len(extra_checks) > 5:
                        print(f"     ... 还有 {len(extra_checks) - 5} 个额外字段")

            print()

        # 打印失败测试的详细信息
        if failed > 0:
            print("=" * 80)
            print("失败测试详情")
            print("=" * 80)
            for result in self.results:
                if result.status == TestStatus.FAILED:
                    print(f"\nAPI: {result.api_name}")
                    print(f"端点: {result.endpoint}")
                    print(f"消息: {result.message}")
                    print(f"响应示例: {json.dumps(result.response_sample, indent=2, ensure_ascii=False)[:500]}")

    def save_report(self, filename: str = "api_test_report.json"):
        """保存测试报告到文件"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.status == TestStatus.PASSED),
                "failed": sum(1 for r in self.results if r.status == TestStatus.FAILED),
                "warning": sum(1 for r in self.results if r.status == TestStatus.WARNING),
            },
            "results": []
        }

        for result in self.results:
            report["results"].append({
                "api_name": result.api_name,
                "endpoint": result.endpoint,
                "status": result.status.value,
                "response_code": result.response_code,
                "message": result.message,
                "field_checks": [
                    {
                        "field_name": fc.field_name,
                        "status": fc.status.value,
                        "expected_type": fc.expected_type,
                        "actual_type": fc.actual_type,
                        "message": fc.message,
                        "found_in_response": fc.found_in_response
                    }
                    for fc in result.field_checks
                ]
            })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n测试报告已保存到: {filename}")


def main():
    """主函数"""
    import sys

    # 检查服务是否可用
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ PhoenixA 服务正常运行")
        else:
            print(f"⚠ 服务健康检查返回状态码: {response.status_code}")
    except Exception as e:
        print(f"✗ 无法连接到 PhoenixA 服务: {str(e)}")
        print(f"  请确保服务已启动并运行在 {BASE_URL}")
        sys.exit(1)

    print()

    # 创建测试器并运行测试
    tester = PhoenixAAPITester()
    tester.run_all_tests()
    tester.print_summary()
    tester.save_report()

    # 根据测试结果设置退出码
    failed = sum(1 for r in tester.results if r.status == TestStatus.FAILED)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

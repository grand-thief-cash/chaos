"""
Unit tests for financial statement task post_process logic.

Tests the data transformation from SDK DataFrame to PhoenixA-compatible dicts,
covering all 5 statement types and edge cases.
"""
import json
import numpy as np
import pandas as pd
import pytest

from artemis.engines.task_engine.download.zh.base_financial_statement import (
    BaseFinancialStatementTask,
    METADATA_FIELDS,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_balance_sheet import StockZHABalanceSheet
from artemis.engines.task_engine.download.zh.stock_zh_a_cash_flow import StockZHACashFlow
from artemis.engines.task_engine.download.zh.stock_zh_a_income import StockZHAIncome
from artemis.engines.task_engine.download.zh.stock_zh_a_profit_express import StockZHAProfitExpress
from artemis.engines.task_engine.download.zh.stock_zh_a_profit_notice import StockZHAProfitNotice


# ── Helpers ──────────────────────────────────────────

class _FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(msg)

    def warning(self, msg):
        self.messages.append(msg)

    def debug(self, msg):
        self.messages.append(msg)


class _FakeCtx:
    """Minimal TaskContext mock for post_process testing."""
    def __init__(self):
        self.run_id = "test-run-001"
        self.logger = _FakeLogger()
        self.status = None
        self.error = None
        self.failed_phase = None

    def fail(self, msg, phase=''):
        self.error = str(msg)
        self.failed_phase = phase

    def has_failed(self):
        return self.error is not None


def _make_balance_sheet_df():
    """Simulate a balance sheet DataFrame from AmazingData SDK."""
    return pd.DataFrame([{
        'MARKET_CODE': '000001.SZ',
        'SECURITY_NAME': '平安银行',
        'STATEMENT_TYPE': '1',
        'REPORT_TYPE': '4',
        'REPORTING_PERIOD': '20231231',
        'ANN_DATE': '20240320',
        'ACTUAL_ANN_DATE': '20240320',
        'COMP_TYPE_CODE': 2,
        'TOTAL_ASSETS': 5600000000000.0,
        'TOTAL_LIAB': 5100000000000.0,
        'CAP_STOCK': 19405918198.0,
        'CURRENCY_CODE': np.nan,  # NaN should be excluded from data_json
        'GOODWILL': 0.0,
    }])


def _make_cashflow_df():
    return pd.DataFrame([{
        'MARKET_CODE': '600519.SH',
        'SECURITY_NAME': '贵州茅台',
        'STATEMENT_TYPE': '1',
        'REPORT_TYPE': '4',
        'REPORTING_PERIOD': '20231231',
        'ANN_DATE': '20240329',
        'ACTUAL_ANN_DATE': '20240329',
        'COMP_TYPE_CODE': 1,
        'CURRENCY_CODE': 'CNY',
        'NET_CASH_FLOWS_OPERA_ACT': 70000000000.0,
        'CASH_RECP_SG_AND_RS': 140000000000.0,
        'IS_CALCULATION': 0,
    }])


def _make_income_df():
    return pd.DataFrame([{
        'MARKET_CODE': '600519.SH',
        'SECURITY_NAME': '贵州茅台',
        'STATEMENT_TYPE': '1',
        'REPORT_TYPE': '4',
        'REPORTING_PERIOD': '20231231',
        'ANN_DATE': '20240329',
        'ACTUAL_ANN_DATE': '20240329',
        'COMP_TYPE_CODE': 1,
        'OPERA_REV': 150000000000.0,
        'NET_PRO_INCL_MIN_INT_INC': 75000000000.0,
        'BASIC_EPS': 59.49,
    }])


def _make_profit_express_df():
    """profit_express returns a single DataFrame, not dict."""
    return pd.DataFrame([{
        'MARKET_CODE': '000001.SZ',
        'REPORTING_PERIOD': '20231231',
        'ANN_DATE': '20240115',
        'ACTUAL_ANN_DATE': '20240115',
        'TOTAL_ASSETS': 5600000000000.0,
        'NET_PRO_EXCL_MIN_INT_INC': 46000000000.0,
        'TOT_OPERA_REV': 180000000000.0,
        'EPS_BASIC': 2.37,
        'IS_AUDIT': 0.0,
        'PERFORMANCE_SUMMARY': '归属于上市公司股东的净利润同比增长2.1%',
    }])


def _make_profit_notice_df():
    """profit_notice returns a single DataFrame, not dict."""
    return pd.DataFrame([{
        'MARKET_CODE': '600519.SH',
        'SECURITY_NAME': '贵州茅台',
        'P_TYPECODE': '10',
        'REPORTING_PERIOD': '20231231',
        'ANN_DATE': '20240115',
        'REPORT_TYPE': '4',
        'P_CHANGE_MAX': 20.5,
        'P_CHANGE_MIN': 15.3,
        'NET_PROFIT_MAX': 8000000.0,
        'NET_PROFIT_MIN': 7500000.0,
        'P_NUMBER': 1.0,
        'P_REASON': '主营业务收入增长',
        'P_SUMMARY': '预计净利润同比增长15%-20%',
    }])


# ── Tests ────────────────────────────────────────────

class TestBalanceSheetPostProcess:

    def test_basic_transform(self):
        task = StockZHABalanceSheet()
        ctx = _FakeCtx()
        result = {'000001.SZ': _make_balance_sheet_df()}

        processed = task.post_process(ctx, result)

        assert len(processed) == 1
        rec = processed[0]
        assert rec['symbol'] == '000001.SZ'
        assert rec['market'] == 'zh_a'
        assert rec['statement_type'] == 'balance_sheet'
        assert rec['reporting_period'] == '20231231'
        assert rec['report_type'] == '4'
        assert rec['statement_code'] == '1'
        assert rec['security_name'] == '平安银行'
        assert rec['ann_date'] == '20240320'
        assert rec['actual_ann_date'] == '20240320'
        assert rec['comp_type_code'] == 2

        # Verify data_json
        data = json.loads(rec['data_json'])
        assert data['TOTAL_ASSETS'] == 5600000000000.0
        assert data['TOTAL_LIAB'] == 5100000000000.0
        assert data['CAP_STOCK'] == 19405918198.0
        assert data['GOODWILL'] == 0.0
        # NaN should be excluded
        assert 'CURRENCY_CODE' not in data

    def test_metadata_fields_excluded_from_data_json(self):
        task = StockZHABalanceSheet()
        ctx = _FakeCtx()
        result = {'000001.SZ': _make_balance_sheet_df()}

        processed = task.post_process(ctx, result)
        data = json.loads(processed[0]['data_json'])

        for field in METADATA_FIELDS:
            assert field not in data, f"{field} should not be in data_json"

    def test_empty_result(self):
        task = StockZHABalanceSheet()
        ctx = _FakeCtx()
        assert task.post_process(ctx, {}) == []

    def test_empty_dataframe(self):
        task = StockZHABalanceSheet()
        ctx = _FakeCtx()
        result = {'000001.SZ': pd.DataFrame()}
        assert task.post_process(ctx, result) == []

    def test_missing_reporting_period_skipped(self):
        task = StockZHABalanceSheet()
        ctx = _FakeCtx()
        df = _make_balance_sheet_df()
        df.at[0, 'REPORTING_PERIOD'] = ''
        result = {'000001.SZ': df}
        assert task.post_process(ctx, result) == []

    def test_missing_market_code_skipped(self):
        task = StockZHABalanceSheet()
        ctx = _FakeCtx()
        df = _make_balance_sheet_df()
        df.at[0, 'MARKET_CODE'] = ''
        result = {'000001.SZ': df}
        assert task.post_process(ctx, result) == []

    def test_numpy_types_converted(self):
        """Ensure numpy float64/int64 are converted to native Python types."""
        task = StockZHABalanceSheet()
        ctx = _FakeCtx()
        df = _make_balance_sheet_df()
        # Ensure columns are numpy types
        df['TOTAL_ASSETS'] = df['TOTAL_ASSETS'].astype(np.float64)
        result = {'000001.SZ': df}
        processed = task.post_process(ctx, result)
        data = json.loads(processed[0]['data_json'])
        # json.dumps would fail if numpy types weren't converted
        assert isinstance(data['TOTAL_ASSETS'], float)


class TestCashFlowPostProcess:

    def test_basic_transform(self):
        task = StockZHACashFlow()
        ctx = _FakeCtx()
        result = {'600519.SH': _make_cashflow_df()}

        processed = task.post_process(ctx, result)

        assert len(processed) == 1
        rec = processed[0]
        assert rec['statement_type'] == 'cashflow'
        assert rec['symbol'] == '600519.SH'
        data = json.loads(rec['data_json'])
        assert data['NET_CASH_FLOWS_OPERA_ACT'] == 70000000000.0
        # CURRENCY_CODE is str 'CNY', not NaN — should be in data_json
        assert data['CURRENCY_CODE'] == 'CNY'
        assert data['IS_CALCULATION'] == 0


class TestIncomePostProcess:

    def test_basic_transform(self):
        task = StockZHAIncome()
        ctx = _FakeCtx()
        result = {'600519.SH': _make_income_df()}

        processed = task.post_process(ctx, result)

        assert len(processed) == 1
        rec = processed[0]
        assert rec['statement_type'] == 'income'
        data = json.loads(rec['data_json'])
        assert data['OPERA_REV'] == 150000000000.0
        assert data['BASIC_EPS'] == 59.49


class TestProfitExpressPostProcess:

    def test_single_dataframe_result(self):
        """profit_express returns DataFrame, not dict."""
        task = StockZHAProfitExpress()
        ctx = _FakeCtx()
        result = _make_profit_express_df()

        processed = task.post_process(ctx, result)

        assert len(processed) == 1
        rec = processed[0]
        assert rec['statement_type'] == 'profit_express'
        assert rec['symbol'] == '000001.SZ'
        # These fields are absent from profit_express SDK data
        assert rec['report_type'] == ''
        assert rec['statement_code'] == ''
        assert rec['security_name'] == ''
        assert rec['comp_type_code'] == 0

        data = json.loads(rec['data_json'])
        assert data['TOTAL_ASSETS'] == 5600000000000.0
        assert data['EPS_BASIC'] == 2.37
        assert 'PERFORMANCE_SUMMARY' in data

    def test_dict_result_also_works(self):
        """In case SDK returns dict, should still work."""
        task = StockZHAProfitExpress()
        ctx = _FakeCtx()
        result = {'all': _make_profit_express_df()}

        processed = task.post_process(ctx, result)
        assert len(processed) == 1

    def test_none_result_returns_empty(self):
        task = StockZHAProfitExpress()
        ctx = _FakeCtx()
        assert task.post_process(ctx, None) == []


class TestProfitNoticePostProcess:

    def test_single_dataframe_result(self):
        task = StockZHAProfitNotice()
        ctx = _FakeCtx()
        result = _make_profit_notice_df()

        processed = task.post_process(ctx, result)

        assert len(processed) == 1
        rec = processed[0]
        assert rec['statement_type'] == 'profit_notice'
        assert rec['symbol'] == '600519.SH'
        assert rec['report_type'] == '4'
        assert rec['security_name'] == '贵州茅台'
        assert rec['statement_code'] == ''
        assert rec['actual_ann_date'] == ''
        assert rec['comp_type_code'] == 0

        data = json.loads(rec['data_json'])
        assert data['P_TYPECODE'] == '10'
        assert data['P_CHANGE_MAX'] == 20.5
        assert data['NET_PROFIT_MAX'] == 8000000.0
        assert data['P_REASON'] == '主营业务收入增长'
        # SECURITY_NAME is in METADATA_FIELDS so should NOT be in data_json
        assert 'SECURITY_NAME' not in data
        # REPORT_TYPE is in METADATA_FIELDS so should NOT be in data_json
        assert 'REPORT_TYPE' not in data


class TestFieldMapping:
    """Verify Artemis output field names match PhoenixA model exactly."""

    PHOENIXA_JSON_FIELDS = {
        'source', 'symbol', 'market', 'statement_type',
        'reporting_period', 'report_type', 'statement_code',
        'security_name', 'ann_date', 'actual_ann_date',
        'comp_type_code', 'data_json',
    }

    @pytest.mark.parametrize("task_cls,result_factory", [
        (StockZHABalanceSheet, lambda: {'000001.SZ': _make_balance_sheet_df()}),
        (StockZHACashFlow, lambda: {'600519.SH': _make_cashflow_df()}),
        (StockZHAIncome, lambda: {'600519.SH': _make_income_df()}),
        (StockZHAProfitExpress, _make_profit_express_df),
        (StockZHAProfitNotice, _make_profit_notice_df),
    ])
    def test_output_fields_match_phoenixa_model(self, task_cls, result_factory):
        """Every record produced by post_process must have exactly the fields
        that PhoenixA's FinancialStatement model expects."""
        task = task_cls()
        ctx = _FakeCtx()
        result = result_factory()

        processed = task.post_process(ctx, result)
        assert len(processed) > 0, f"{task_cls.__name__} produced no records"

        for rec in processed:
            assert set(rec.keys()) == self.PHOENIXA_JSON_FIELDS, (
                f"{task_cls.__name__} field mismatch: "
                f"extra={set(rec.keys()) - self.PHOENIXA_JSON_FIELDS}, "
                f"missing={self.PHOENIXA_JSON_FIELDS - set(rec.keys())}"
            )

    @pytest.mark.parametrize("task_cls,result_factory", [
        (StockZHABalanceSheet, lambda: {'000001.SZ': _make_balance_sheet_df()}),
        (StockZHACashFlow, lambda: {'600519.SH': _make_cashflow_df()}),
        (StockZHAIncome, lambda: {'600519.SH': _make_income_df()}),
        (StockZHAProfitExpress, _make_profit_express_df),
        (StockZHAProfitNotice, _make_profit_notice_df),
    ])
    def test_data_json_is_valid_json(self, task_cls, result_factory):
        """data_json must be a valid JSON string."""
        task = task_cls()
        ctx = _FakeCtx()
        result = result_factory()

        processed = task.post_process(ctx, result)
        for rec in processed:
            data = json.loads(rec['data_json'])
            assert isinstance(data, dict)

    @pytest.mark.parametrize("task_cls,result_factory", [
        (StockZHABalanceSheet, lambda: {'000001.SZ': _make_balance_sheet_df()}),
        (StockZHACashFlow, lambda: {'600519.SH': _make_cashflow_df()}),
        (StockZHAIncome, lambda: {'600519.SH': _make_income_df()}),
        (StockZHAProfitExpress, _make_profit_express_df),
        (StockZHAProfitNotice, _make_profit_notice_df),
    ])
    def test_data_json_excludes_metadata(self, task_cls, result_factory):
        """data_json must NOT contain any METADATA_FIELDS."""
        task = task_cls()
        ctx = _FakeCtx()
        result = result_factory()

        processed = task.post_process(ctx, result)
        for rec in processed:
            data = json.loads(rec['data_json'])
            for field in METADATA_FIELDS:
                assert field not in data, (
                    f"{task_cls.__name__}: {field} leaked into data_json"
                )


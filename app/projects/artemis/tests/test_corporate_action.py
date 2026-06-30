"""
Unit tests for corporate action task post_process logic (dividend, right_issue).
"""
import json
from typing import cast
import pandas as pd
import pytest

from artemis.core import TaskContext
from artemis.engines.task_engine.download.zh.stock_zh_a_dividend import StockZHADividend
from artemis.engines.task_engine.download.zh.stock_zh_a_right_issue import StockZHARightIssue


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
    def __init__(self):
        self.run_id = "test-run-corp"
        self.logger = _FakeLogger()
        self.error = None
        self.failed_phase = None

    def fail(self, msg, phase=''):
        self.error = str(msg)
        self.failed_phase = phase

    def has_failed(self):
        return self.error is not None


def _as_task_context(ctx: _FakeCtx) -> TaskContext:
    return cast(TaskContext, cast(object, ctx))


def _make_dividend_df():
    return pd.DataFrame([{
        'MARKET_CODE': '600519.SH',
        'DIV_PROGRESS': '3',
        'DVD_PER_SHARE_STK': 0.0,
        'DVD_PER_SHARE_PRE_TAX_CASH': 27.46,
        'DVD_PER_SHARE_AFTER_TAX_CASH': 24.714,
        'DATE_EQY_RECORD': '20240618',
        'DATE_EX': '20240619',
        'DATE_DVD_PAYOUT': '20240619',
        'DIV_PRELANDATE': '20240329',
        'ANN_DATE': '20240618',
        'REPORT_PERIOD': '20231231',
        'CURRENCY_CODE': 'CNY',
        'DIV_BASESHARE': 125619.78,
        'IS_CHANGED': 0,
        'DIV_BONUSRATE': 0.0,
        'DIV_CONVERSEDRATE': 0.0,
        'REMARK': '',
    }])


def _make_right_issue_df():
    return pd.DataFrame([{
        'MARKET_CODE': '601988.SH',
        'PROGRESS': 3,
        'PRICE': 3.12,
        'RATIO': 0.18,
        'AMT_PLAN': 500000.0,
        'AMT_REAL': 480000.0,
        'COLLECTION_FUND': 1497600000.0,
        'SHAREB_REG_DATE': '20240115',
        'EX_DIVIDEND_DATE': '20240116',
        'LISTED_DATE': '20240125',
        'PREPLAN_DATE': '20231001',
        'ANN_DATE': '20240115',
        'RIGHTSISSUE_YEAR': '2024',
        'RIGHTSISSUE_NAME': '601988配股',
        'RATIO_DENOMINATOR': 10.0,
        'RATIO_MOLECULAR': 1.8,
    }])


# ── Dividend Tests ───────────────────────────────────

class TestDividendPostProcess:

    def test_basic_transform(self):
        task = StockZHADividend()
        ctx = _FakeCtx()
        result = _make_dividend_df()

        processed = task.post_process(_as_task_context(ctx), result)

        assert len(processed) == 1
        rec = processed[0]
        assert rec['symbol'] == '600519'
        assert rec['market'] == 'zh_a'
        assert rec['action_type'] == 'dividend'
        assert rec['report_period'] == '2023-12-31'
        assert rec['ann_date'] == '2024-06-18'
        assert rec['progress_code'] == '3'

        data = json.loads(rec['data_json'])
        assert data['DVD_PER_SHARE_PRE_TAX_CASH'] == 27.46
        assert data['DVD_PER_SHARE_AFTER_TAX_CASH'] == 24.714
        assert data['CURRENCY_CODE'] == 'CNY'
        assert data['DATE_EX'] == '20240619'

    def test_metadata_excluded_from_data_json(self):
        task = StockZHADividend()
        ctx = _FakeCtx()
        result = _make_dividend_df()

        processed = task.post_process(_as_task_context(ctx), result)
        data = json.loads(processed[0]['data_json'])

        # MARKET_CODE, ANN_DATE are base metadata
        assert 'MARKET_CODE' not in data
        assert 'ANN_DATE' not in data
        # REPORT_PERIOD and DIV_PROGRESS are task-specific metadata
        assert 'REPORT_PERIOD' not in data
        assert 'DIV_PROGRESS' not in data

    def test_empty_result(self):
        task = StockZHADividend()
        ctx = _FakeCtx()
        assert task.post_process(_as_task_context(ctx), pd.DataFrame()) == []

    def test_none_result(self):
        task = StockZHADividend()
        ctx = _FakeCtx()
        assert task.post_process(_as_task_context(ctx), None) == []

    def test_missing_market_code_skipped(self):
        task = StockZHADividend()
        ctx = _FakeCtx()
        df = _make_dividend_df()
        df.at[0, 'MARKET_CODE'] = ''
        assert task.post_process(_as_task_context(ctx), df) == []


# ── Right Issue Tests ────────────────────────────────

class TestRightIssuePostProcess:

    def test_basic_transform(self):
        task = StockZHARightIssue()
        ctx = _FakeCtx()
        result = _make_right_issue_df()

        processed = task.post_process(_as_task_context(ctx), result)

        assert len(processed) == 1
        rec = processed[0]
        assert rec['symbol'] == '601988'
        assert rec['action_type'] == 'right_issue'
        assert rec['report_period'] == '2024'
        assert rec['ann_date'] == '2024-01-15'
        assert rec['progress_code'] == '3'

        data = json.loads(rec['data_json'])
        assert data['PRICE'] == 3.12
        assert data['RATIO'] == 0.18
        assert data['COLLECTION_FUND'] == 1497600000.0
        assert data['RIGHTSISSUE_NAME'] == '601988配股'

    def test_metadata_excluded_from_data_json(self):
        task = StockZHARightIssue()
        ctx = _FakeCtx()
        result = _make_right_issue_df()

        processed = task.post_process(_as_task_context(ctx), result)
        data = json.loads(processed[0]['data_json'])

        assert 'MARKET_CODE' not in data
        assert 'ANN_DATE' not in data
        assert 'RIGHTSISSUE_YEAR' not in data
        assert 'PROGRESS' not in data


# ── Cross-cutting Field Mapping Tests ────────────────

class TestCorporateActionFieldMapping:
    """Verify Artemis output fields match PhoenixA CorporateAction model."""

    PHOENIXA_JSON_FIELDS = {
        'source', 'symbol', 'market', 'action_type',
        'report_period', 'ann_date', 'progress_code', 'data_json',
    }

    @pytest.mark.parametrize("task_cls,result_factory", [
        (StockZHADividend, _make_dividend_df),
        (StockZHARightIssue, _make_right_issue_df),
    ])
    def test_output_fields_match_phoenixa_model(self, task_cls, result_factory):
        task = task_cls()
        ctx = _FakeCtx()
        result = result_factory()

        processed = task.post_process(_as_task_context(ctx), result)
        assert len(processed) > 0

        for rec in processed:
            assert set(rec.keys()) == self.PHOENIXA_JSON_FIELDS, (
                f"{task_cls.__name__} field mismatch: "
                f"extra={set(rec.keys()) - self.PHOENIXA_JSON_FIELDS}, "
                f"missing={self.PHOENIXA_JSON_FIELDS - set(rec.keys())}"
            )

    @pytest.mark.parametrize("task_cls,result_factory", [
        (StockZHADividend, _make_dividend_df),
        (StockZHARightIssue, _make_right_issue_df),
    ])
    def test_data_json_is_valid_json(self, task_cls, result_factory):
        task = task_cls()
        ctx = _FakeCtx()
        processed = task.post_process(_as_task_context(ctx), result_factory())
        for rec in processed:
            data = json.loads(rec['data_json'])
            assert isinstance(data, dict)

    @pytest.mark.parametrize("task_cls,result_factory", [
        (StockZHADividend, _make_dividend_df),
        (StockZHARightIssue, _make_right_issue_df),
    ])
    def test_data_json_excludes_all_metadata(self, task_cls, result_factory):
        task = task_cls()
        ctx = _FakeCtx()
        processed = task.post_process(_as_task_context(ctx), result_factory())
        all_meta = task._get_all_metadata_fields()
        for rec in processed:
            data = json.loads(rec['data_json'])
            for field in all_meta:
                assert field not in data, f"{task_cls.__name__}: {field} in data_json"


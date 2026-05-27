from typing import cast

import pandas as pd

from artemis.core import TaskContext
from artemis.engines.task_engine.download.zh.stock_zh_a_long_hu_bang import StockZHALongHuBang


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
        self.run_id = "test-run-long-hu-bang"
        self.logger = _FakeLogger()
        self.error = None
        self.failed_phase = None

    def fail(self, msg, phase=''):
        self.error = str(msg)
        self.failed_phase = phase


def _as_task_context(ctx: _FakeCtx) -> TaskContext:
    return cast(TaskContext, cast(object, ctx))


def _make_df():
    return pd.DataFrame([
        {
            'MARKET_CODE': '000001.SZ',
            'TRADE_DATE': '20260527',
            'SECURITY_NAME': '平安银行',
            'REASON_TYPE': '1001',
            'REASON_TYPE_NAME': '日涨幅偏离值达7%',
            'CHANGE_RANGE': 9.98,
            'TRADER_NAME': '国泰君安证券上海分公司',
            'BUY_AMOUNT': 123456789.12,
            'SELL_AMOUNT': 98765432.1,
            'FLOW_MARK': 1,
            'TOTAL_AMOUNT': 24680246.8,
            'TOTAL_VOLUME': 321.5,
        }
    ])


class TestLongHuBangPostProcess:
    def test_basic_transform(self):
        task = StockZHALongHuBang()
        ctx = _FakeCtx()

        processed = task.post_process(_as_task_context(ctx), _make_df())

        assert len(processed) == 1
        rec = processed[0]
        assert rec['source'] == 'amazing_data'
        assert rec['symbol'] == '000001'
        assert rec['market'] == 'zh_a'
        assert rec['trade_date'] == '2026-05-27'
        assert rec['reason_type'] == '1001'
        assert rec['trader_name'] == '国泰君安证券上海分公司'
        assert rec['flow_mark'] == 1
        assert rec['security_name'] == '平安银行'
        assert rec['reason_type_name'] == '日涨幅偏离值达7%'
        assert rec['change_range'] == 9.98
        assert rec['buy_amount'] == 123456789.12
        assert rec['sell_amount'] == 98765432.1
        assert rec['total_amount'] == 24680246.8
        assert rec['total_volume'] == 321.5

    def test_deduplicate_last_record_wins(self):
        task = StockZHALongHuBang()
        ctx = _FakeCtx()
        df = pd.concat([_make_df(), _make_df()], ignore_index=True)
        df.at[1, 'BUY_AMOUNT'] = 999.0

        processed = task.post_process(_as_task_context(ctx), df)

        assert len(processed) == 1
        assert processed[0]['buy_amount'] == 999.0

    def test_invalid_rows_are_skipped(self):
        task = StockZHALongHuBang()
        ctx = _FakeCtx()
        df = _make_df()
        df.at[0, 'TRADER_NAME'] = ''

        assert task.post_process(_as_task_context(ctx), df) == []





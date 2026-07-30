from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from artemis.consts import TaskCode
from artemis.engines.task_engine.download.zh.stock_zh_a_minute_child import (
    StockZhAMinuteChild,
    parse_baostock_minute_time,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_minute_parent import StockZhAMinuteParent


class Logger:
    def __init__(self):
        self.events = []

    def info(self, event):
        self.events.append(event)

    def warning(self, event):
        self.events.append(event)


class Context(SimpleNamespace):
    def __init__(self, params):
        super().__init__(params=params, run_id="minute-test", logger=Logger(), failed=[])

    def fail(self, message, phase=None):
        self.failed.append((message, phase))


def test_parse_baostock_minute_time_preserves_intraday_timestamp():
    assert parse_baostock_minute_time("20260729093500000", "2026-07-29") == (
        "2026-07-29T09:35:00.000+08:00"
    )


def test_parse_baostock_minute_time_rejects_date_mismatch():
    try:
        parse_baostock_minute_time("20260729093500000", "2026-07-28")
    except ValueError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("date mismatch must fail")


def test_minute_post_process_rejects_invalid_ohlc_and_deduplicates():
    child = StockZhAMinuteChild()
    ctx = Context({"symbol": "600183"})
    frame = pd.DataFrame([
        {"date": "2026-07-29", "time": "20260729093500000", "security_id": 1, "symbol": "600183", "open": "10", "high": "10.2", "low": "9.9", "close": "10.1", "volume": "100", "amount": "1000"},
        {"date": "2026-07-29", "time": "20260729093500000", "security_id": 1, "symbol": "600183", "open": "10.1", "high": "10.3", "low": "10", "close": "10.2", "volume": "200", "amount": "2000"},
        {"date": "2026-07-29", "time": "20260729094000000", "security_id": 1, "symbol": "600183", "open": "11", "high": "10", "low": "9", "close": "9.5", "volume": "1", "amount": "1"},
    ])

    bars = child.post_process(ctx, frame)

    assert len(bars) == 1
    assert bars.iloc[0]["trade_date"] == "2026-07-29T09:35:00.000+08:00"
    assert bars.iloc[0]["close"] == 10.2
    assert ctx.logger.events[-1]["rejected_count"] == 1


def test_minute_parent_replays_watermark_day():
    parent = StockZhAMinuteParent()
    ctx = Context({
        "period": "min5",
        "adjust": "nf",
        "start_date": "2026-07-01",
        "end_date": "2026-07-29",
        "fields": "date,time,open,high,low,close,volume,amount,adjustflag",
        "symbol_infos": {1: {"security_id": 1, "symbol": "600183", "exchange": "SH"}},
        "last_updates_map": {1: "2026-07-28T15:00:00+08:00"},
    })

    specs = parent.plan(ctx)

    assert len(specs) == 1
    assert specs[0]["key"] == TaskCode.STOCK_ZH_A_MINUTE_CHILD
    assert specs[0]["params"]["start_date"] == "2026-07-28"
    assert specs[0]["params"]["bs_period"] == "5"

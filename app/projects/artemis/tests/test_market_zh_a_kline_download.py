from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from artemis.consts import DeptServices, TaskCode
from artemis.engines.task_engine.download.zh.market_zh_a_kline_child import (
    MarketZhAKlineChild,
    amazing_data_bar_available_at,
)
from artemis.engines.task_engine.download.zh.market_zh_a_kline_parent import (
    MarketZhAKlineParent,
)


class _Logger:
    def __init__(self):
        self.events = []

    def info(self, event):
        self.events.append(event)


class _Context(SimpleNamespace):
    def __init__(self, params):
        super().__init__(
            params=params,
            incoming_params=params,
            run_id="ad-kline-test",
            logger=_Logger(),
            failed=[],
        )

    def fail(self, message, phase=None):
        self.failed.append((message, phase))


def test_amazing_data_forward_label_becomes_complete_bar_time():
    assert amazing_data_bar_available_at(
        "2026-07-30 09:30:00", "min1"
    ) == "2026-07-30T09:31:00.000+08:00"
    assert amazing_data_bar_available_at(
        "2026-07-30 09:35:00", "min5"
    ) == "2026-07-30T09:40:00.000+08:00"
    assert amazing_data_bar_available_at(
        "2026-07-30", "daily"
    ) == "2026-07-30"


def test_amazing_data_parent_batches_incremental_registry_securities():
    parent = MarketZhAKlineParent()
    ctx = _Context(
        {
            "asset_type": "stock",
            "period": "min1",
            "adjust": "nf",
            "end_date": "2026-07-30",
            "max_symbols_per_child": 50,
            "selected_securities": {
                7: {
                    "security_id": 7,
                    "symbol": "600183",
                    "exchange": "SH",
                }
            },
            "effective_start_dates": {7: "2026-07-29"},
        }
    )

    specs = parent.plan(ctx)

    assert len(specs) == 1
    assert specs[0]["key"] == TaskCode.MARKET_ZH_A_KLINE_CHILD
    assert specs[0]["params"]["start_date"] == "2026-07-29"
    assert specs[0]["params"]["securities"]["600183.SH"]["security_id"] == 7


def test_amazing_data_parent_resolves_registry_and_replays_watermark_day():
    class _Phoenix:
        def get_security_by_id(self, security_id):
            assert security_id == 7
            return {
                "security_id": 7,
                "symbol": "600183",
                "exchange": "SH",
                "asset_type": "stock",
                "market": "zh_a",
            }

        def get_bars_last_update(self, **kwargs):
            assert kwargs["security_ids"] == [7]
            assert kwargs["period"] == "min5"
            return {7: "2026-07-29T14:55:00+08:00"}

    parent = MarketZhAKlineParent()
    ctx = _Context(
        {
            "asset_type": "stock",
            "period": "min5",
            "adjust": "nf",
            "security_ids": [7],
            "start_date": "2026-07-01",
            "end_date": "2026-07-30",
        }
    )
    ctx.dept_http = {DeptServices.PHOENIXA: _Phoenix()}

    parent.load_dynamic_parameters(ctx)

    assert ctx.failed == []
    assert ctx.params["selected_securities"][7]["symbol"] == "600183"
    assert ctx.params["effective_start_dates"][7] == "2026-07-29"


def test_amazing_data_child_normalizes_frame_and_rejects_bad_ohlc():
    child = MarketZhAKlineChild()
    ctx = _Context(
        {
            "asset_type": "stock",
            "period": "min1",
            "adjust": "nf",
            "securities": {
                "600183.SH": {"security_id": 7, "symbol": "600183"}
            },
        }
    )
    frame = pd.DataFrame(
        [
            {
                "kline_time": "2026-07-30 09:30:00",
                "open": 10,
                "high": 10.2,
                "low": 9.9,
                "close": 10.1,
                "volume": 100,
                "amount": 1005,
            },
            {
                "kline_time": "2026-07-30 09:31:00",
                "open": 11,
                "high": 10,
                "low": 9.8,
                "close": 9.9,
                "volume": 1,
                "amount": 10,
            },
        ]
    )

    bars = child.post_process(ctx, {"600183.SH": frame})

    assert len(bars) == 1
    assert bars[0]["trade_date"] == "2026-07-30T09:31:00.000+08:00"
    assert bars[0]["security_id"] == 7
    assert bars[0]["volume"] == 100
    assert ctx.logger.events[-1]["rejected_count"] == 1

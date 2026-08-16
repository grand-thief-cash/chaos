from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from artemis.consts import DeptServices
from artemis.engines.task_engine.download.zh.stock_zh_a_level1_file import (
    StockZhALevel1File,
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
            run_id="level1-file-test",
            logger=_Logger(),
            failed=[],
            stats={},
        )

    def fail(self, message, phase=None):
        self.failed.append((str(message), phase))


def test_level1_file_task_resolves_registry_stock(tmp_path):
    class _Phoenix:
        def get_securities(self, **kwargs):
            assert kwargs["symbols"] == ["600183"]
            return {
                4889: {
                    "security_id": 4889,
                    "symbol": "600183",
                    "exchange": "SH",
                    "asset_type": "stock",
                    "market": "zh_a",
                }
            }

    task = StockZhALevel1File()
    ctx = _Context(
        {
            "symbols": "600183",
            "start_date": "2026-08-14",
            "end_date": "2026-08-14",
            "storage_root": str(tmp_path),
        }
    )
    ctx.dept_http = {DeptServices.PHOENIXA: _Phoenix()}

    task.load_dynamic_parameters(ctx)

    assert ctx.failed == []
    assert ctx.params["selected_securities"][4889]["symbol"] == "600183"
    assert ctx.params["storage_root"] == str(tmp_path.resolve())


def test_level1_file_task_writes_atomic_parquet_manifest_and_skips_complete(tmp_path):
    class _MarketData:
        def __init__(self):
            self.calls = 0

        def query_snapshot(self, code_list, begin_date, end_date):
            self.calls += 1
            assert code_list == ["600183.SH"]
            assert begin_date == end_date == 20260814
            return {
                "sh600183": pd.DataFrame(
                    {
                        "last_price": [140.0, 140.1],
                        "bid_price1": [139.99, 140.09],
                        "ask_price1": [140.01, 140.11],
                        "bid_volume1": [1200, 1300],
                        "ask_volume1": [800, 700],
                    },
                    index=pd.to_datetime(
                        ["2026-08-14 09:30:00", "2026-08-14 09:30:03"]
                    ),
                )
            }

    params = {
        "selected_securities": {
            4889: {
                "security_id": 4889,
                "symbol": "600183",
                "exchange": "SH",
            }
        },
        "start_date": "2026-08-14",
        "end_date": "2026-08-14",
        "storage_root": str(tmp_path),
        "force": False,
    }
    market_data = _MarketData()
    task = StockZhALevel1File()
    task._market_data = market_data
    ctx = _Context(params)

    task.sink(ctx, task.execute(ctx))

    partition = tmp_path / "security_id=4889" / "trade_date=2026-08-14"
    data_path = partition / "snapshot.parquet"
    manifest = json.loads((partition / "manifest.json").read_text(encoding="utf-8"))
    stored = pd.read_parquet(data_path)
    assert market_data.calls == 1
    assert manifest["status"] == "complete"
    assert manifest["row_count"] == 2
    assert manifest["median_cadence_seconds"] == 3.0
    assert stored["meta_security_id"].tolist() == [4889, 4889]
    assert ctx.stats["partition_written"] == 1

    second_ctx = _Context(dict(params))
    task.sink(second_ctx, task.execute(second_ctx))

    assert market_data.calls == 1
    assert second_ctx.stats["partition_written"] == 0


def test_frame_for_code_accepts_nested_date_bucket():
    frame = pd.DataFrame({"last_price": [10.0, 10.1]})
    other = pd.DataFrame({"last_price": [20.0]})

    selected = StockZhALevel1File._frame_for_code(
        {"20260814": {"000001.SZ": other, "600183.SH": frame}},
        "600183.SH",
        "600183",
    )

    assert selected.equals(frame)

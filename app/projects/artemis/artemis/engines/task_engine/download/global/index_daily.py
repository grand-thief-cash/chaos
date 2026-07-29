from __future__ import annotations

from typing import Any, Dict, List

import akshare as ak
import pandas as pd

from artemis.core import TaskContext
from .bar_utils import (
    configured_specs,
    resolve_bar_specs,
    sink_bars_by_asset_type,
)
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    optional_number,
    rate_limited_call,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


class GlobalIndexDaily(WorkerUnit):
    """Download only configured global indexes already present in registry."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        specs = configured_specs(ctx.params or {}, "indexes")
        if not specs:
            ctx.fail(
                "GLOBAL_INDEX_DAILY requires an indexes whitelist",
                phase="load_dynamic_parameters",
            )
            return
        ctx.params["pending_specs"] = resolve_bar_specs(
            ctx,
            specs,
            default_asset_type="index",
        )

    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for spec in (ctx.params or {}).get("pending_specs", []):
            source_api = str(
                spec.get("source_api") or "index_global_hist_em",
            )
            source_symbol = str(
                spec.get("source_symbol")
                or (
                    spec["name"]
                    if source_api == "index_global_hist_em"
                    else spec["symbol"]
                ),
            )
            if source_api == "index_global_hist_em":
                downloader = lambda source_symbol=source_symbol: (
                    ak.index_global_hist_em(symbol=source_symbol)
                )
            elif source_api == "stock_hk_index_daily_sina":
                downloader = lambda source_symbol=source_symbol: (
                    ak.stock_hk_index_daily_sina(symbol=source_symbol)
                )
            else:
                ctx.fail(
                    f"unsupported global index source_api: {source_api}",
                    phase="execute",
                )
                continue
            result[spec["symbol"]] = {
                "spec": spec,
                "frame": rate_limited_call(
                    ctx,
                    f"{source_api}:{source_symbol}",
                    downloader,
                ),
            }
        return result

    def post_process(
        self,
        ctx: TaskContext,
        result: Any,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        end_date = date_string(
            (ctx.params or {}).get("end_date") or pd.Timestamp.now(),
        )
        for item in result.values() if isinstance(result, dict) else []:
            spec, frame = item["spec"], item["frame"]
            if not isinstance(frame, pd.DataFrame):
                continue
            source_api = str(
                spec.get("source_api") or "index_global_hist_em",
            )
            for record in frame.to_dict("records"):
                if source_api == "stock_hk_index_daily_sina":
                    trade_date = date_string(record.get("date"))
                    values = {
                        "open": optional_number(record.get("open")),
                        "high": optional_number(record.get("high")),
                        "low": optional_number(record.get("low")),
                        "close": optional_number(record.get("close")),
                    }
                    raw_volume = optional_number(record.get("volume"))
                    volume = (
                        None
                        if raw_volume is None
                        else int(round(raw_volume))
                    )
                    preclose = None
                    pct_chg = None
                else:
                    trade_date = date_string(record.get("日期"))
                    values = {
                        "open": optional_number(record.get("今开")),
                        "high": optional_number(record.get("最高")),
                        "low": optional_number(record.get("最低")),
                        "close": optional_number(record.get("最新价")),
                    }
                    volume = None
                    preclose = optional_number(record.get("昨收"))
                    pct_chg = optional_number(record.get("涨跌幅"))
                if (
                    not trade_date
                    or trade_date < spec["effective_start_date"]
                    or trade_date > end_date
                    or any(value is None for value in values.values())
                ):
                    continue
                rows.append({
                    "asset_type": "index",
                    "security_id": spec["security_id"],
                    "trade_date": trade_date,
                    **values,
                    "volume": volume,
                    "amount": None,
                    "preclose": preclose,
                    "pct_chg": pct_chg,
                })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        sink_bars_by_asset_type(ctx, rows)

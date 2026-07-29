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


class GlobalCommodityDaily(WorkerUnit):
    """Download a configured international-futures whitelist into standard Bars."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        specs = configured_specs(ctx.params or {}, "symbols")
        if not specs:
            ctx.fail(
                "GLOBAL_COMMODITY_DAILY requires a symbols whitelist",
                phase="load_dynamic_parameters",
            )
            return
        ctx.params["pending_specs"] = resolve_bar_specs(
            ctx,
            specs,
            default_asset_type="futures",
        )

    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for spec in (ctx.params or {}).get("pending_specs", []):
            symbol = spec["symbol"]
            result[symbol] = {
                "spec": spec,
                "frame": rate_limited_call(
                    ctx,
                    f"futures_global_hist_em:{symbol}",
                    lambda symbol=symbol:
                    ak.futures_global_hist_em(symbol=symbol),
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
            for record in frame.to_dict("records"):
                trade_date = date_string(record.get("日期"))
                values = {
                    "open": optional_number(record.get("开盘")),
                    "high": optional_number(record.get("最高")),
                    "low": optional_number(record.get("最低")),
                    "close": optional_number(record.get("最新价")),
                }
                if (
                    not trade_date
                    or trade_date < spec["effective_start_date"]
                    or trade_date > end_date
                    or any(value is None for value in values.values())
                ):
                    continue
                volume_value = optional_number(record.get("总量"))
                rows.append({
                    "asset_type": "futures",
                    "security_id": spec["security_id"],
                    "trade_date": trade_date,
                    **values,
                    "volume": (
                        None
                        if volume_value is None
                        else int(round(volume_value))
                    ),
                    "amount": None,
                    "preclose": None,
                    "pct_chg": optional_number(record.get("涨幅")),
                })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        sink_bars_by_asset_type(ctx, rows)

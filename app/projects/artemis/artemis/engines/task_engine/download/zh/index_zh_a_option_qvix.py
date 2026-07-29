from __future__ import annotations

from typing import Any, Dict, List, cast

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    incremental_start_date,
    optional_number,
    rate_limited_call,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


QVIX_APIS = {
    "50ETF": ("index_option_50etf_qvix", ak.index_option_50etf_qvix),
    "300ETF": ("index_option_300etf_qvix", ak.index_option_300etf_qvix),
    "500ETF": ("index_option_500etf_qvix", ak.index_option_500etf_qvix),
    "CYB": ("index_option_cyb_qvix", ak.index_option_cyb_qvix),
    "KCB": ("index_option_kcb_qvix", ak.index_option_kcb_qvix),
    "100ETF": ("index_option_100etf_qvix", ak.index_option_100etf_qvix),
    "300INDEX": ("index_option_300index_qvix", ak.index_option_300index_qvix),
    "1000INDEX": ("index_option_1000index_qvix", ak.index_option_1000index_qvix),
    "50INDEX": ("index_option_50index_qvix", ak.index_option_50index_qvix),
}


def _symbols(value: Any) -> List[str]:
    if isinstance(value, str):
        result = [item.strip().upper() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        result = [str(item).strip().upper() for item in value if str(item).strip()]
    else:
        result = []
    return list(dict.fromkeys(result or QVIX_APIS.keys()))


class IndexZhAOptionQVIX(WorkerUnit):
    """All supported AKShare daily QVIX series with per-symbol watermarks."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        symbols = _symbols(ctx.params.get("symbols"))
        unsupported = [symbol for symbol in symbols if symbol not in QVIX_APIS]
        if unsupported:
            ctx.fail(f"unsupported QVIX symbols: {unsupported}", phase="load_dynamic_parameters")
            return
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        last_updates = phoenix.get_qvix_last_updates(symbols)
        ctx.params["symbols"] = symbols
        ctx.params["effective_start_dates"] = {
            symbol: incremental_start_date(
                ctx.params.get("start_date"),
                last_updates.get(symbol),
                "2015-01-01",
            )
            for symbol in symbols
        }

    def execute(self, ctx: TaskContext):
        end_date = date_string(ctx.params.get("end_date") or pd.Timestamp.now())
        result = {}
        for symbol in ctx.params["symbols"]:
            if ctx.params["effective_start_dates"][symbol] > end_date:
                continue
            api_name, downloader = QVIX_APIS[symbol]
            result[symbol] = rate_limited_call(ctx, api_name, downloader)
        return result

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        end_date = date_string(ctx.params.get("end_date") or pd.Timestamp.now())
        rows: List[Dict[str, Any]] = []
        for symbol, frame in result.items():
            if not isinstance(frame, pd.DataFrame):
                continue
            start_date = ctx.params["effective_start_dates"][symbol]
            for record in frame.to_dict("records"):
                trade_date = date_string(record.get("date"))
                if not trade_date or trade_date < start_date or trade_date > end_date:
                    continue
                values = {
                    field: optional_number(record.get(field))
                    for field in ("open", "high", "low", "close")
                }
                if any(value is None for value in values.values()):
                    continue
                rows.append({
                    "symbol": symbol,
                    "trade_date": trade_date,
                    **values,
                })
        rows.sort(key=lambda row: (row["symbol"], row["trade_date"]))
        ctx.logger.info({
            "event": "index_zh_a_option_qvix_post_process",
            "row_count": len(rows),
            "symbols": ctx.params["symbols"],
            "run_id": ctx.run_id,
        })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        if not phoenix.upsert_qvix_daily(rows=rows, run_id=ctx.run_id):
            ctx.fail("failed to sink QVIX daily data", phase="sink")

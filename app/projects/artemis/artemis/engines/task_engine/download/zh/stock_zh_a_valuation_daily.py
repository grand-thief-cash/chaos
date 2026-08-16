from __future__ import annotations

from typing import Any, Dict, List

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    incremental_start_date,
    optional_number,
    rate_limited_call,
)
from artemis.engines.task_engine.download.zh.utils import get_security_map_for_task
from artemis.engines.task_engine.worker_unit import WorkerUnit


SOURCE = "eastmoney_valuation"
FIELD_MAP = {
    "当日收盘价": ("valuation_close", "cny"),
    "当日涨跌幅": ("valuation_pct_change", "percent"),
    "总市值": ("valuation_market_cap", "cny"),
    "流通市值": ("valuation_float_cap", "cny"),
    "总股本": ("valuation_total_shares", "share"),
    "流通股本": ("valuation_float_shares", "share"),
    "PE(TTM)": ("valuation_pe_ttm", "multiple"),
    "PE(静)": ("valuation_pe_static", "multiple"),
    "市净率": ("valuation_pb", "multiple"),
    "PEG值": ("valuation_peg", "multiple"),
    "市现率": ("valuation_pcf", "multiple"),
    "市销率": ("valuation_ps", "multiple"),
}


class StockZHAValuationDaily(WorkerUnit):
    """Slow, resumable EastMoney daily valuation history downloader."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        security_map = get_security_map_for_task(ctx)
        securities = sorted(
            security_map.values(), key=lambda row: (row["symbol"], row["security_id"]),
        )
        # Deduplicate because security_map is keyed by SDK code.
        securities = list({int(row["security_id"]): row for row in securities}.values())
        offset = max(int(params.get("symbol_offset", 0)), 0)
        max_symbols = min(max(int(params.get("max_symbols_per_run", 5)), 1), 100)
        securities = securities[offset:offset + max_symbols]
        if not securities:
            ctx.fail("no registered securities selected", phase="load_dynamic_parameters")
            return
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        last_updates = phoenix.get_market_observation_last_updates(
            source=SOURCE,
            security_ids=[int(row["security_id"]) for row in securities],
        )
        end_date = date_string(params.get("end_date") or pd.Timestamp.now())
        pending = []
        for row in securities:
            security_id = int(row["security_id"])
            effective_start = incremental_start_date(
                params.get("start_date"), last_updates.get(security_id), "2010-01-01",
            )
            if effective_start <= end_date:
                pending.append({**row, "effective_start_date": effective_start})
        ctx.params["pending_securities"] = pending
        ctx.params["effective_end_date"] = end_date

    def execute(self, ctx: TaskContext):
        result: Dict[int, Any] = {}
        for security in (ctx.params or {}).get("pending_securities", []):
            security_id = int(security["security_id"])
            symbol = str(security["symbol"])
            result[security_id] = rate_limited_call(
                ctx,
                f"stock_value_em:{symbol}",
                lambda symbol=symbol: ak.stock_value_em(symbol=symbol),
            )
        return result

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        pending = {
            int(row["security_id"]): row
            for row in (ctx.params or {}).get("pending_securities", [])
        }
        end_date = str((ctx.params or {}).get("effective_end_date") or "")
        rows: List[Dict[str, Any]] = []
        for security_id, frame in result.items():
            security = pending.get(int(security_id))
            if not security or not isinstance(frame, pd.DataFrame):
                continue
            for record in frame.to_dict("records"):
                trade_date = date_string(record.get("数据日期"))
                if (
                    not trade_date
                    or trade_date < security["effective_start_date"]
                    or trade_date > end_date
                ):
                    continue
                for source_field, (observation_type, unit) in FIELD_MAP.items():
                    value = optional_number(record.get(source_field))
                    if value is None:
                        continue
                    rows.append({
                        "security_id": int(security_id),
                        "trade_date": trade_date,
                        "observation_type": observation_type,
                        "value": value,
                        "unit": unit,
                        "extra_json": {
                            "symbol": security["symbol"],
                            "source_field": source_field,
                        },
                    })
        rows.sort(key=lambda row: (
            row["security_id"], row["trade_date"], row["observation_type"],
        ))
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        for start in range(0, len(rows), 1000):
            if not phoenix.upsert_market_observations(
                source=SOURCE,
                rows=rows[start:start + 1000],
                run_id=ctx.run_id,
            ):
                ctx.fail("failed to sink valuation observations", phase="sink")
                return

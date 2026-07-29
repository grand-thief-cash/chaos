from __future__ import annotations

from typing import Any, Dict, List

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    incremental_start_date,
    rate_limited_call,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


class StockZhANotice(WorkerUnit):
    """Bounded CNInfo announcement metadata loader; original URLs are retained."""

    def execute(self, ctx: TaskContext):
        params = ctx.params or {}
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        requested = params.get("symbols")
        if isinstance(requested, str):
            requested = [s.strip() for s in requested.split(",") if s.strip()]
        registry = phoenix.get_securities(
            symbols=requested or None,
            asset_type="stock",
            market="zh_a",
            limit=20000,
        )
        securities = sorted(registry.values(), key=lambda row: row["symbol"])
        offset = max(int(params.get("symbol_offset", 0)), 0)
        max_symbols = max(int(params.get("max_symbols_per_run", 20)), 1)
        securities = securities[offset:offset + max_symbols]
        if not securities:
            ctx.fail("no registered securities selected for notice download", phase="execute")
            return {}
        self._security_by_symbol = {row["symbol"]: row for row in securities}

        end = date_string(params.get("end_date") or pd.Timestamp.now())
        last_updates = phoenix.get_security_event_last_updates(
            source="cninfo",
            event_type="notice",
            security_ids=[
                int(row["security_id"])
                for row in securities
            ],
        )
        effective_starts = {
            row["symbol"]: incremental_start_date(
                params.get("start_date"),
                last_updates.get(int(row["security_id"])),
                "2026-01-01",
            )
            for row in securities
        }
        ctx.params["effective_start_dates"] = effective_starts
        category = str(params.get("category", ""))
        return {
            row["symbol"]: rate_limited_call(
                ctx,
                f"stock_zh_a_disclosure_report_cninfo:{row['symbol']}",
                lambda row=row: ak.stock_zh_a_disclosure_report_cninfo(
                    symbol=row["symbol"],
                    market="沪深京",
                    keyword="",
                    category=category,
                    start_date=effective_starts[row["symbol"]].replace("-", ""),
                    end_date=end.replace("-", ""),
                ),
            )
            for row in securities
            if effective_starts[row["symbol"]] <= end
        }

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not isinstance(result, dict):
            return events
        security_by_symbol = getattr(self, "_security_by_symbol", {})
        starts = (ctx.params or {}).get("effective_start_dates", {})
        end_date = date_string((ctx.params or {}).get("end_date") or pd.Timestamp.now())
        for symbol, frame in result.items():
            security = security_by_symbol.get(symbol)
            if not security or not isinstance(frame, pd.DataFrame):
                continue
            for record in frame.to_dict("records"):
                event_date = date_string(record.get("公告时间"))
                title = str(record.get("公告标题", "")).strip()
                if (
                    not event_date
                    or event_date < starts.get(symbol, "")
                    or event_date > end_date
                    or not title
                ):
                    continue
                events.append({
                    "security_id": int(security["security_id"]),
                    "event_date": event_date,
                    "title": title,
                    "url": str(record.get("公告链接", "")).strip(),
                    "data_json": {
                        "symbol": symbol,
                        "security_name": str(record.get("简称", "")).strip(),
                        "category": str((ctx.params or {}).get("category", "")),
                    },
                })
        return events

    def sink(self, ctx: TaskContext, events: List[Dict[str, Any]]) -> None:
        if not events:
            return
        payload = [{**row, "data_json": row["data_json"]} for row in events]
        ok = ctx.dept_http[DeptServices.PHOENIXA].upsert_security_events(
            source="cninfo",
            event_type="notice",
            rows=payload,
            run_id=ctx.run_id,
        )
        if not ok:
            ctx.fail("failed to sink CNInfo notices", phase="sink")

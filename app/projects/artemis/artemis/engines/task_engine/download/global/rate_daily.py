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
from artemis.engines.task_engine.worker_unit import WorkerUnit
from .series import RATE_SERIES


class GlobalRateDaily(WorkerUnit):
    """Persist every bond_zh_us_rate value column as vertical observations."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        symbols = [spec["symbol"] for spec in RATE_SERIES]
        registry = phoenix.get_securities(
            symbols=symbols,
            asset_type="macro",
            market="global",
            limit=100,
        )
        by_symbol = {
            row["symbol"]: row
            for row in registry.values()
        }
        missing = [
            symbol for symbol in symbols
            if symbol not in by_symbol
        ]
        if missing:
            ctx.fail(
                "rate identities missing from security_registry; "
                f"run GLOBAL_SECURITY_LIST first: {missing}",
                phase="load_dynamic_parameters",
            )
            return
        last_updates = phoenix.get_market_observation_last_updates(
            source="akshare",
            security_ids=[
                int(by_symbol[symbol]["security_id"])
                for symbol in symbols
            ],
        )
        end_date = date_string(
            (ctx.params or {}).get("end_date") or pd.Timestamp.now(),
        )
        pending: List[Dict[str, Any]] = []
        for spec in RATE_SERIES:
            security_id = int(by_symbol[spec["symbol"]]["security_id"])
            effective_start = incremental_start_date(
                (ctx.params or {}).get("start_date"),
                last_updates.get(security_id),
                "2015-01-01",
            )
            if effective_start <= end_date:
                pending.append({
                    **spec,
                    "security_id": security_id,
                    "effective_start_date": effective_start,
                })
        ctx.params["pending_series"] = pending

    def execute(self, ctx: TaskContext):
        pending = (ctx.params or {}).get("pending_series", [])
        if not pending:
            return pd.DataFrame()
        start_date = min(
            spec["effective_start_date"]
            for spec in pending
        )
        return rate_limited_call(
            ctx,
            "bond_zh_us_rate",
            lambda: ak.bond_zh_us_rate(
                start_date=start_date.replace("-", ""),
            ),
        )

    def post_process(
        self,
        ctx: TaskContext,
        result: Any,
    ) -> List[Dict[str, Any]]:
        if not isinstance(result, pd.DataFrame):
            return []
        pending = (ctx.params or {}).get("pending_series", [])
        end_date = date_string(
            (ctx.params or {}).get("end_date") or pd.Timestamp.now(),
        )
        rows: List[Dict[str, Any]] = []
        for record in result.to_dict("records"):
            trade_date = date_string(record.get("日期"))
            if not trade_date or trade_date > end_date:
                continue
            for spec in pending:
                if trade_date < spec["effective_start_date"]:
                    continue
                value = optional_number(record.get(spec["source_field"]))
                if value is None:
                    continue
                rows.append({
                    "security_id": spec["security_id"],
                    "trade_date": trade_date,
                    "observation_type": spec["observation_type"],
                    "value": value,
                    "unit": spec["unit"],
                    "extra_json": {
                        "source_field": spec["source_field"],
                    },
                })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        if not phoenix.upsert_market_observations(
            source="akshare",
            rows=rows,
            run_id=ctx.run_id,
        ):
            ctx.fail("failed to sink global rate observations", phase="sink")

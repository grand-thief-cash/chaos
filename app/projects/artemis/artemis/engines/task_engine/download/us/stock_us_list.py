from __future__ import annotations

from typing import Any, Dict, List

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.risk_download_utils import (
    rate_limited_call,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


US_EXCHANGE_BY_PREFIX = {
    "105": "NASDAQ",
    "106": "NYSE",
    "107": "AMEX",
}


class StockUSList(WorkerUnit):
    """Refresh the full EastMoney US-stock identity snapshot incrementally."""

    def execute(self, ctx: TaskContext):
        return rate_limited_call(
            ctx,
            "stock_us_spot_em",
            ak.stock_us_spot_em,
        )

    def post_process(
        self,
        ctx: TaskContext,
        result: Any,
    ) -> List[Dict[str, Any]]:
        if not isinstance(result, pd.DataFrame):
            return []
        rows: List[Dict[str, Any]] = []
        for record in result.to_dict("records"):
            source_symbol = str(record.get("代码") or "").strip().upper()
            if "." not in source_symbol:
                continue
            prefix, symbol = source_symbol.split(".", 1)
            exchange = US_EXCHANGE_BY_PREFIX.get(prefix)
            name = str(record.get("名称") or "").strip()
            if not exchange or not symbol or not name:
                continue
            rows.append({
                "symbol": symbol,
                "name": name,
                "exchange": exchange,
                "asset_type": "stock",
                "market": "us",
                "status": "active",
            })
        return list({
            (row["exchange"], row["symbol"]): row
            for row in rows
        }.values())

    @staticmethod
    def _changed_rows(
        downloaded: List[Dict[str, Any]],
        existing: Dict[tuple[str, str], Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        changed: List[Dict[str, Any]] = []
        for row in downloaded:
            current = existing.get((row["exchange"], row["symbol"]))
            if current is None or any(
                str(current.get(field, "")) != str(row[field])
                for field in ("name", "status")
            ):
                changed.append(row)
        return changed

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        registry = phoenix.get_securities(
            asset_type="stock",
            market="us",
            limit=20000,
        )
        existing = {
            (row["exchange"], row["symbol"]): row
            for row in registry.values()
        }
        changed = self._changed_rows(rows, existing)
        ctx.stats["downloaded_identity_count"] = len(rows)
        ctx.stats["changed_identity_count"] = len(changed)
        if changed and not phoenix.upsert_securities(
            changed,
            run_id=ctx.run_id,
        ):
            ctx.fail(
                "failed to incrementally update US security registry",
                phase="sink",
            )

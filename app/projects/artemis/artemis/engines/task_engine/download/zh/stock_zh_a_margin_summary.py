from __future__ import annotations

from typing import Any, Dict, List, cast

import AmazingData as ad
import pandas as pd

from artemis.consts import DeptServices, SDK_NAME
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.core.sdk.manager import sdk_mgr
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    incremental_start_date,
    optional_number,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


MARGIN_FIELDS = {
    "SUM_BORROW_MONEY_BALANCE": "financing_balance",
    "SUM_PURCH_WITH_BORROW_MONEY": "financing_buy",
    "SUM_REPAYMENT_OF_BORROW_MONEY": "financing_repay",
    "SUM_SEC_LENDING_BALANCE": "securities_balance",
    "SUM_SALES_OF_BORROWED_SEC": "securities_sell_volume",
    "SUM_MARGIN_TRADE_BALANCE": "margin_total_balance",
}


class StockZhAMarginSummary(WorkerUnit):
    """AmazingData market-wide margin summary, incremented from PhoenixA."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        last_update = phoenix.get_margin_summary_last_update()
        ctx.params["effective_start_date"] = incremental_start_date(
            ctx.params.get("start_date"),
            last_update,
            "2015-01-01",
        )
        ctx.params["last_update"] = last_update

    def before_execute(self, ctx: TaskContext) -> None:
        try:
            sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
            self._info_data = ad.InfoData()
        except Exception as exc:
            ctx.fail(
                f"failed to acquire AmazingData InfoData: {exc}",
                phase="before_execute",
            )

    def execute(self, ctx: TaskContext):
        start_date = ctx.params["effective_start_date"]
        end_date = date_string(ctx.params.get("end_date") or pd.Timestamp.now())
        if start_date > end_date:
            return pd.DataFrame()
        # is_local=False calls AmazingData directly. No persistent cache directory
        # is configured for this task.
        return self._info_data.get_margin_summary(
            is_local=False,
            begin_date=int(start_date.replace("-", "")),
            end_date=int(end_date.replace("-", "")),
        )

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        if not isinstance(result, pd.DataFrame):
            return []
        start_date = ctx.params["effective_start_date"]
        end_date = date_string(ctx.params.get("end_date") or pd.Timestamp.now())
        rows_by_date: Dict[str, Dict[str, Any]] = {}
        for record in result.to_dict("records"):
            trade_date = date_string(record.get("TRADE_DATE"))
            if not trade_date or trade_date < start_date or trade_date > end_date:
                continue
            # AmazingData returns one row per market for the same trade date but
            # does not expose a market identifier. This table is explicitly the
            # whole-market summary, so aggregate those additive fields by date.
            row = rows_by_date.setdefault(
                trade_date,
                {"trade_date": trade_date},
            )
            for source_field, target_field in MARGIN_FIELDS.items():
                value = optional_number(record.get(source_field))
                if value is not None:
                    row[target_field] = row.get(target_field, 0.0) + value
        rows = [rows_by_date[key] for key in sorted(rows_by_date)]
        ctx.logger.info({
            "event": "stock_zh_a_margin_summary_post_process",
            "row_count": len(rows),
            "effective_start_date": start_date,
            "run_id": ctx.run_id,
        })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        if not phoenix.upsert_margin_summary(rows=rows, run_id=ctx.run_id):
            ctx.fail("failed to sink margin summary", phase="sink")

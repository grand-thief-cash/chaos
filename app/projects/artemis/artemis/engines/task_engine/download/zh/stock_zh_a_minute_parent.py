from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, cast

import baostock as bs

from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.download.zh.utils import convert_to_baostock_params
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit


class StockZhAMinuteParent(OrchestratorUnit):
    """Plan per-security BaoStock minute downloads.

    Intraday watermarks intentionally replay the watermark's trading date. A
    minute source may have exposed an incomplete final session, while upsert on
    (symbol, timestamp) makes the overlap idempotent.
    """

    SUPPORTED_PERIODS = {"min5", "min15", "min30", "min60"}

    def parameter_check(self, ctx: TaskContext) -> None:
        period = str((ctx.incoming_params or {}).get("period", "")).strip()
        adjust = str((ctx.incoming_params or {}).get("adjust", "")).strip()
        if not period or not adjust:
            ctx.fail(
                f"Missing required input params: period={period}, adjust={adjust}",
                phase="parameter_check",
            )

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        symbol_list = str(params.get("symbol_list", "") or "").strip()
        symbols = [item.strip() for item in symbol_list.split(",") if item.strip()]
        exchange_text = str(params.get("exchange", "") or "").strip()
        exchanges = [item.strip().upper() for item in exchange_text.split(",") if item.strip()] or None

        client = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        symbol_infos = client.get_securities(symbols=symbols or None, exchanges=exchanges)
        security_ids = [
            int(info["security_id"])
            for info in symbol_infos.values()
            if info.get("security_id")
        ]
        last_updates = client.get_bars_last_update(
            period=str(params.get("period", "")),
            adjust=str(params.get("adjust", "")),
            security_ids=security_ids or None,
        )
        ctx.params["symbol_infos"] = symbol_infos
        ctx.params["last_updates_map"] = last_updates

    def before_execute(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        period = str(params.get("period", ""))
        adjust = str(params.get("adjust", ""))
        start_date = str(params.get("start_date", ""))
        end_date = str(params.get("end_date") or datetime.now().strftime("%Y-%m-%d"))
        fields = str(params.get("fields", ""))

        if period not in self.SUPPORTED_PERIODS:
            ctx.fail(f"unsupported BaoStock minute period: {period}", phase="before_execute")
            return
        if adjust != "nf":
            ctx.fail("minute execution data must use adjust=nf", phase="before_execute")
            return
        if not start_date or not fields:
            ctx.fail("start_date and fields are required", phase="before_execute")
            return
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            ctx.fail("start_date/end_date must be YYYY-MM-DD", phase="before_execute")
            return
        if start > end:
            ctx.fail("start_date must be <= end_date", phase="before_execute")
            return

        login = bs.login()
        if getattr(login, "error_code", None) != "0":
            ctx.fail(
                f"baostock login failed: {getattr(login, 'error_msg', 'unknown error')}",
                phase="before_execute",
            )

    @staticmethod
    def _watermark_date(value: Any) -> str | None:
        text = str(value or "").strip()
        if len(text) < 10:
            return None
        candidate = text[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
        except ValueError:
            return None
        return candidate

    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        params = ctx.params or {}
        period = str(params.get("period", ""))
        adjust = str(params.get("adjust", ""))
        start_date = str(params.get("start_date", ""))
        end_date = str(params.get("end_date") or datetime.now().strftime("%Y-%m-%d"))
        fields = str(params.get("fields", ""))
        symbol_infos = params.get("symbol_infos", {}) or {}
        last_updates = params.get("last_updates_map", {}) or {}

        frequency = convert_to_baostock_params("frequency", period)
        adjust_flag = convert_to_baostock_params("adjustflag", adjust)
        if not frequency or not adjust_flag:
            ctx.fail(
                f"invalid BaoStock mapping: period={period}, adjust={adjust}",
                phase="plan",
            )
            return []

        child_specs: List[Dict[str, Any]] = []
        for info in symbol_infos.values():
            symbol = str(info.get("symbol", "")).strip()
            exchange = str(info.get("exchange", "")).strip().upper()
            security_id = int(info.get("security_id") or 0)
            if not symbol or exchange not in {"SH", "SZ", "BJ"} or security_id <= 0:
                ctx.fail(
                    f"invalid security identity: symbol={symbol}, exchange={exchange}, security_id={security_id}",
                    phase="plan",
                )
                return []

            item_start = start_date
            watermark_date = self._watermark_date(last_updates.get(security_id))
            if watermark_date and watermark_date > item_start:
                item_start = watermark_date
            if item_start > end_date:
                continue

            child_specs.append({
                "key": TaskCode.STOCK_ZH_A_MINUTE_CHILD,
                "params": {
                    "bs_code": f"{exchange.lower()}.{symbol}",
                    "symbol": symbol,
                    "security_id": security_id,
                    "start_date": item_start,
                    "end_date": end_date,
                    "period": period,
                    "adjust": adjust,
                    "bs_period": frequency,
                    "bs_adjust": adjust_flag,
                    "fields": fields,
                },
            })

        ctx.logger.info({
            "event": "stock_zh_a_minute_parent_plan_complete",
            "run_id": ctx.run_id,
            "total_symbols": len(symbol_infos),
            "generated_tasks": len(child_specs),
            "period": period,
        })
        return child_specs

    def finalize(self, ctx: TaskContext) -> None:
        bs.logout()

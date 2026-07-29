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
from artemis.engines.task_engine.download.us.stock_us_list import (
    US_EXCHANGE_BY_PREFIX,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


US_PREFIX_BY_EXCHANGE = {
    exchange: prefix
    for prefix, exchange in US_EXCHANGE_BY_PREFIX.items()
}


def _list_param(value: Any) -> List[str]:
    if isinstance(value, str):
        return [item.strip().upper() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    return []


class StockUSDaily(WorkerUnit):
    """Download an explicit US symbol/exchange selection from security_registry."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        symbols = _list_param(params.get("symbols"))
        exchanges = _list_param(params.get("exchanges"))
        if not symbols and not exchanges:
            ctx.fail(
                "STOCK_US_DAILY requires symbols or exchanges",
                phase="load_dynamic_parameters",
            )
            return
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        registry = phoenix.get_securities(
            symbols=symbols or None,
            exchanges=exchanges or None,
            asset_type="stock",
            market="us",
            status="active",
            limit=20000,
        )
        securities = sorted(
            registry.values(),
            key=lambda row: (row["exchange"], row["symbol"]),
        )
        if symbols:
            visible = {row["symbol"] for row in securities}
            missing = [symbol for symbol in symbols if symbol not in visible]
            if missing:
                ctx.fail(
                    "US identities missing from security_registry; "
                    f"run STOCK_US_LIST first: {missing}",
                    phase="load_dynamic_parameters",
                )
                return
        offset = max(int(params.get("symbol_offset") or 0), 0)
        max_symbols = max(int(params.get("max_symbols_per_run") or 20), 1)
        securities = securities[offset:offset + max_symbols]
        last_updates = phoenix.get_bars_last_update(
            asset_type="stock",
            market="us",
            period="daily",
            adjust="nf",
            security_ids=[
                int(row["security_id"])
                for row in securities
            ],
        ) if securities else {}
        end_date = date_string(params.get("end_date") or pd.Timestamp.now())
        pending: List[Dict[str, Any]] = []
        for security in securities:
            start_date = incremental_start_date(
                params.get("start_date"),
                last_updates.get(int(security["security_id"])),
                "2015-01-01",
            )
            if start_date <= end_date:
                pending.append({
                    **security,
                    "effective_start_date": start_date,
                })
        ctx.params["pending_securities"] = pending

    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        end_date = date_string(
            (ctx.params or {}).get("end_date") or pd.Timestamp.now(),
        )
        result: Dict[str, Any] = {}
        for security in (ctx.params or {}).get("pending_securities", []):
            prefix = US_PREFIX_BY_EXCHANGE.get(security["exchange"])
            if not prefix:
                ctx.fail(
                    f"unsupported US exchange: {security['exchange']}",
                    phase="execute",
                )
                continue
            source_symbol = f"{prefix}.{security['symbol']}"
            start_date = security["effective_start_date"]
            result[security["symbol"]] = {
                "security": security,
                "frame": rate_limited_call(
                    ctx,
                    f"stock_us_hist:{source_symbol}",
                    lambda source_symbol=source_symbol, start_date=start_date:
                    ak.stock_us_hist(
                        symbol=source_symbol,
                        period="daily",
                        start_date=start_date.replace("-", ""),
                        end_date=end_date.replace("-", ""),
                        adjust="",
                    ),
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
            security, frame = item["security"], item["frame"]
            if not isinstance(frame, pd.DataFrame):
                continue
            for record in frame.to_dict("records"):
                trade_date = date_string(record.get("日期"))
                values = {
                    "open": optional_number(record.get("开盘")),
                    "high": optional_number(record.get("最高")),
                    "low": optional_number(record.get("最低")),
                    "close": optional_number(record.get("收盘")),
                }
                if (
                    not trade_date
                    or trade_date < security["effective_start_date"]
                    or trade_date > end_date
                    or any(value is None for value in values.values())
                ):
                    continue

                def optional_int(field: str):
                    value = optional_number(record.get(field))
                    return None if value is None else int(round(value))

                rows.append({
                    "security_id": int(security["security_id"]),
                    "trade_date": trade_date,
                    **values,
                    "volume": optional_int("成交量"),
                    "amount": optional_int("成交额"),
                    "preclose": None,
                    "pct_chg": optional_number(record.get("涨跌幅")),
                })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        if not phoenix.upsert_bars(
            asset_type="stock",
            market="us",
            period="daily",
            adjust="nf",
            source="akshare",
            bars=rows,
            run_id=ctx.run_id,
        ):
            ctx.fail("failed to sink US stock bars", phase="sink")

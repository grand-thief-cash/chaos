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


OPTION_APIS = {
    "SSE": ("option_daily_stats_sse", ak.option_daily_stats_sse),
    "SZSE": ("option_daily_stats_szse", ak.option_daily_stats_szse),
}

REGISTRY_EXCHANGES = {
    "SSE": "SH",
    "SZSE": "SZ",
}


def _exchanges(value: Any) -> List[str]:
    if isinstance(value, str):
        result = [item.strip().upper() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        result = [str(item).strip().upper() for item in value if str(item).strip()]
    else:
        result = []
    return list(dict.fromkeys(result or OPTION_APIS.keys()))


def _optional_int(value: Any) -> int | None:
    number = optional_number(value)
    return None if number is None else int(round(number))


def _symbol(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    number = pd.to_numeric(value, errors="coerce")
    if not pd.isna(number):
        return str(int(number)).zfill(6)
    return str(value).strip()


class OptionZhADailyStats(WorkerUnit):
    """SSE/SZSE option daily statistics, advanced by exchange watermark."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        exchanges = _exchanges(ctx.params.get("exchanges"))
        unsupported = [exchange for exchange in exchanges if exchange not in OPTION_APIS]
        if unsupported:
            ctx.fail(
                f"unsupported option exchanges: {unsupported}",
                phase="load_dynamic_parameters",
            )
            return
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        last_updates = phoenix.get_option_daily_stats_last_updates(exchanges)
        ctx.params["exchanges"] = exchanges
        ctx.params["effective_start_dates"] = {
            exchange: incremental_start_date(
                ctx.params.get("start_date"),
                last_updates.get(exchange),
                "2015-01-01",
            )
            for exchange in exchanges
        }

    def execute(self, ctx: TaskContext):
        end = pd.Timestamp(ctx.params.get("end_date") or pd.Timestamp.now()).normalize()
        max_days = max(int(ctx.params.get("max_days_per_run", 5)), 1)
        result = {}
        for exchange in ctx.params["exchanges"]:
            start = pd.Timestamp(ctx.params["effective_start_dates"][exchange])
            # Process the oldest missing business days first. Repeated daily runs
            # therefore catch up without jumping over gaps.
            dates = list(pd.bdate_range(start, end))[:max_days]
            api_name, downloader = OPTION_APIS[exchange]
            for day in dates:
                api_date = day.strftime("%Y%m%d")
                result[(exchange, day.strftime("%Y-%m-%d"))] = rate_limited_call(
                    ctx,
                    f"{api_name}:{api_date}",
                    lambda downloader=downloader, api_date=api_date:
                    downloader(date=api_date),
                )
        return result

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        rows: List[Dict[str, Any]] = []
        for (exchange, fallback_date), frame in result.items():
            if not isinstance(frame, pd.DataFrame):
                continue
            for record in frame.to_dict("records"):
                trade_date = date_string(record.get("交易日") or fallback_date)
                underlying_symbol = _symbol(record.get("合约标的代码"))
                if not trade_date or not underlying_symbol:
                    continue
                row: Dict[str, Any] = {
                    "exchange": exchange,
                    "underlying_symbol": underlying_symbol,
                    "underlying_name": str(record.get("合约标的名称") or "").strip(),
                    "trade_date": trade_date,
                }
                field_map = {
                    "合约数量": "contract_count",
                    "总成交额": "turnover",
                    "总成交量": "volume",
                    "成交量": "volume",
                    "认购成交量": "call_volume",
                    "认沽成交量": "put_volume",
                    "未平仓合约总数": "open_interest",
                    "未平仓认购合约数": "call_open_interest",
                    "未平仓认沽合约数": "put_open_interest",
                }
                for source_field, target_field in field_map.items():
                    if source_field not in record:
                        continue
                    value = _optional_int(record.get(source_field))
                    if value is not None:
                        row[target_field] = value
                if (value := optional_number(record.get("认沽/认购"))) is not None:
                    row["put_call_volume_ratio"] = value
                if (
                    value := optional_number(record.get("认沽/认购持仓比"))
                ) is not None:
                    row["put_call_open_interest_ratio"] = value
                rows.append(row)
        rows.sort(
            key=lambda row: (
                row["exchange"], row["underlying_symbol"], row["trade_date"],
            ),
        )
        ctx.logger.info({
            "event": "option_zh_a_daily_stats_post_process",
            "row_count": len(rows),
            "exchanges": ctx.params["exchanges"],
            "run_id": ctx.run_id,
        })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        symbols = sorted({str(row["underlying_symbol"]) for row in rows})
        exchanges = sorted({
            REGISTRY_EXCHANGES[str(row["exchange"])]
            for row in rows
        })
        identities: Dict[tuple[str, str], Dict[str, Any]] = {}
        for asset_type in ("etf", "index", "stock"):
            registry = phoenix.get_securities(
                symbols=symbols,
                asset_type=asset_type,
                market="zh_a",
                exchanges=exchanges,
                limit=max(100, len(symbols) * 3),
            )
            for identity in registry.values():
                identities[(
                    str(identity["exchange"]).upper(),
                    str(identity["symbol"]),
                )] = identity

        payload: List[Dict[str, Any]] = []
        missing: List[str] = []
        for row in rows:
            registry_exchange = REGISTRY_EXCHANGES[str(row["exchange"])]
            symbol = str(row["underlying_symbol"])
            identity = identities.get((registry_exchange, symbol))
            if identity is None:
                missing.append(f"{registry_exchange}:{symbol}")
                continue
            item = dict(row)
            item["underlying_security_id"] = int(identity["security_id"])
            item.pop("underlying_symbol", None)
            payload.append(item)

        if missing:
            ctx.fail(
                "option underlyings missing from security_registry; "
                f"run the ETF/index registry task first: {sorted(set(missing))}",
                phase="sink",
            )
            return
        if not phoenix.upsert_option_daily_stats(rows=payload, run_id=ctx.run_id):
            ctx.fail("failed to sink option daily stats", phase="sink")

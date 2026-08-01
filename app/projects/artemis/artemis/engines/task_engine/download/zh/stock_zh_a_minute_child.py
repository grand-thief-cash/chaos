from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import baostock as bs
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.worker_unit import WorkerUnit


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MINUTE_FIELDS = "date,time,open,high,low,close,volume,amount,adjustflag"


def parse_baostock_minute_time(raw_time: object, raw_date: object) -> str:
    text = str(raw_time or "").strip()
    date_text = str(raw_date or "").strip()
    if len(text) != 17 or not text.isdigit():
        raise ValueError(f"invalid BaoStock minute time: {text!r}")
    parsed = datetime.strptime(text, "%Y%m%d%H%M%S%f").replace(tzinfo=SHANGHAI_TZ)
    if date_text and parsed.strftime("%Y-%m-%d") != date_text:
        raise ValueError(f"BaoStock date/time mismatch: date={date_text!r}, time={text!r}")
    return parsed.isoformat(timespec="milliseconds")


class StockZhAMinuteChild(WorkerUnit):
    def execute(self, ctx: TaskContext) -> pd.DataFrame:
        params = ctx.params or {}
        security_id = int(params.get("security_id") or 0)
        symbol = str(params.get("symbol", ""))
        if security_id <= 0:
            ctx.fail(f"missing security_id for symbol={symbol}", phase="execute")
            return pd.DataFrame()

        fields = str(params.get("fields") or MINUTE_FIELDS)
        result = bs.query_history_k_data_plus(
            params.get("bs_code"),
            fields,
            start_date=params.get("start_date"),
            end_date=params.get("end_date"),
            frequency=params.get("bs_period"),
            adjustflag=params.get("bs_adjust"),
        )
        if result.error_code != "0":
            ctx.fail(
                f"baostock minute query failed for {params.get('bs_code')}: "
                f"{result.error_code} {result.error_msg}",
                phase="execute",
            )
            return pd.DataFrame()

        rows = []
        while result.next():
            rows.append(result.get_row_data())
        if not rows:
            return pd.DataFrame()

        frame = pd.DataFrame(rows, columns=[item.strip() for item in fields.split(",")])
        frame["security_id"] = security_id
        frame["symbol"] = symbol
        return frame

    def post_process(self, ctx: TaskContext, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame

        required = {"date", "time", "security_id", "symbol", "open", "high", "low", "close"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            ctx.fail(f"minute data missing fields: {missing}", phase="post_process")
            return pd.DataFrame()

        work = frame.copy()
        timestamps = []
        for raw_time, raw_date in zip(work["time"], work["date"]):
            try:
                timestamps.append(parse_baostock_minute_time(raw_time, raw_date))
            except ValueError:
                timestamps.append(None)
        work["trade_date"] = timestamps

        for column in ("open", "high", "low", "close"):
            work[column] = pd.to_numeric(work[column], errors="coerce").round(4)
        for column in ("volume", "amount"):
            if column in work.columns:
                work[column] = pd.to_numeric(work[column], errors="coerce").round(0).astype("Int64")

        valid = work["trade_date"].notna()
        valid &= work["symbol"].astype(str).str.strip() != ""
        valid &= pd.to_numeric(work["security_id"], errors="coerce").fillna(0) > 0
        valid &= work[["open", "high", "low", "close"]].notna().all(axis=1)
        valid &= work["low"] <= work["high"]
        valid &= work["open"].between(work["low"], work["high"])
        valid &= work["close"].between(work["low"], work["high"])
        if "volume" in work.columns:
            valid &= work["volume"].isna() | (work["volume"] >= 0)
        if "amount" in work.columns:
            valid &= work["amount"].isna() | (work["amount"] >= 0)

        rejected = int((~valid).sum())
        if rejected:
            ctx.logger.warning({
                "event": "stock_zh_a_minute_rows_rejected",
                "run_id": ctx.run_id,
                "symbol": ctx.params.get("symbol"),
                "rejected_count": rejected,
            })

        columns = [
            "security_id", "trade_date", "symbol", "open", "high", "low", "close", "volume", "amount",
        ]
        bars = work.loc[valid, [column for column in columns if column in work.columns]].copy()
        bars = bars.drop_duplicates(subset=["trade_date"], keep="last").sort_values("trade_date")
        return bars.astype(object).where(pd.notna(bars), None).reset_index(drop=True)

    def sink(self, ctx: TaskContext, bars: pd.DataFrame) -> None:
        if bars.empty:
            return
        client: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        ok = client.upsert_bars(
            asset_type="stock",
            market="zh_a",
            period=str(ctx.params.get("period")),
            adjust=str(ctx.params.get("adjust")),
            bars=bars.to_dict("records"),
            run_id=ctx.run_id,
        )
        if not ok:
            ctx.fail(
                f"failed to sink minute bars for symbol={ctx.params.get('symbol')}",
                phase="sink",
            )

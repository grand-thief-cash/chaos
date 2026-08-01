from __future__ import annotations

from datetime import timedelta
from typing import Any

import AmazingData as ad
import pandas as pd

from artemis.consts import DeptServices, SDK_NAME
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.core.sdk.manager import sdk_mgr
from artemis.engines.task_engine.worker_unit import WorkerUnit


PERIOD_MINUTES = {"min1": 1, "min5": 5, "min30": 30}
PERIOD_ATTRS = {**{key: key for key in PERIOD_MINUTES}, "daily": "day"}


def amazing_data_bar_available_at(value: Any, period: str) -> str:
    """Convert AmazingData's forward/start label to canonical bar availability."""
    timestamp = pd.to_datetime(value, errors="raise")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("Asia/Shanghai")
    else:
        timestamp = timestamp.tz_convert("Asia/Shanghai")
    if period in PERIOD_MINUTES:
        timestamp += timedelta(minutes=PERIOD_MINUTES[period])
        return timestamp.isoformat(timespec="milliseconds")
    return timestamp.strftime("%Y-%m-%d")


class MarketZhAKlineChild(WorkerUnit):
    """Download one incremental symbol batch from AmazingData."""

    def before_execute(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        securities = params.get("securities", {}) or {}
        if not securities:
            ctx.fail("securities are required", phase="before_execute")
            return
        try:
            base_data = sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
            self._market_data = ad.MarketData(base_data.get_calendar())
        except Exception as exc:
            ctx.fail(
                f"failed to acquire AmazingData market client: {exc}",
                phase="before_execute",
            )

    def execute(self, ctx: TaskContext) -> dict[str, pd.DataFrame]:
        params = ctx.params or {}
        period = str(params.get("period"))
        period_enum = getattr(
            ad.constant.Period, PERIOD_ATTRS.get(period, ""), None
        )
        if period_enum is None:
            ctx.fail(f"unsupported AmazingData period: {period}", phase="execute")
            return {}
        result = self._market_data.query_kline(
            list((params.get("securities") or {}).keys()),
            begin_date=int(str(params["start_date"]).replace("-", "")),
            end_date=int(str(params["end_date"]).replace("-", "")),
            period=period_enum.value,
        )
        return result if isinstance(result, dict) else {}

    def post_process(
        self, ctx: TaskContext, result: dict[str, pd.DataFrame]
    ) -> list[dict[str, Any]]:
        params = ctx.params or {}
        period = str(params["period"])
        securities = {
            str(code).upper(): info
            for code, info in (params.get("securities") or {}).items()
        }
        bars: list[dict[str, Any]] = []
        rejected = 0
        for raw_code, frame in (result or {}).items():
            code = str(raw_code).upper()
            info = securities.get(code)
            if info is None or not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            work = frame.reset_index()
            time_column = (
                "kline_time"
                if "kline_time" in work.columns
                else work.columns[0]
            )
            for row in work.to_dict("records"):
                try:
                    trade_date = amazing_data_bar_available_at(
                        row.get(time_column), period
                    )
                    values = {
                        field: float(pd.to_numeric(row.get(field), errors="raise"))
                        for field in ("open", "high", "low", "close")
                    }
                    if (
                        values["low"] > values["high"]
                        or not values["low"]
                        <= values["open"]
                        <= values["high"]
                        or not values["low"]
                        <= values["close"]
                        <= values["high"]
                    ):
                        raise ValueError("invalid OHLC")
                    volume_value = pd.to_numeric(
                        row.get("volume"), errors="coerce"
                    )
                    amount_value = pd.to_numeric(
                        row.get("amount"), errors="coerce"
                    )
                    if (
                        not pd.isna(volume_value) and float(volume_value) < 0
                    ) or (
                        not pd.isna(amount_value) and float(amount_value) < 0
                    ):
                        raise ValueError("negative volume or amount")
                except (TypeError, ValueError):
                    rejected += 1
                    continue
                bars.append(
                    {
                        "security_id": int(info["security_id"]),
                        "trade_date": trade_date,
                        "symbol": str(info["symbol"]),
                        **{
                            field: round(value, 4)
                            for field, value in values.items()
                        },
                        "volume": (
                            None
                            if pd.isna(volume_value)
                            else int(round(float(volume_value)))
                        ),
                        "amount": (
                            None
                            if pd.isna(amount_value)
                            else int(round(float(amount_value)))
                        ),
                        "preclose": None,
                        "pct_chg": None,
                    }
                )
        bars.sort(key=lambda item: (item["security_id"], item["trade_date"]))
        deduplicated = {
            (item["security_id"], item["trade_date"]): item for item in bars
        }
        ctx.logger.info(
            {
                "event": "market_zh_a_kline_child_post_process",
                "run_id": ctx.run_id,
                "bar_count": len(deduplicated),
                "rejected_count": rejected,
            }
        )
        return list(deduplicated.values())

    def sink(self, ctx: TaskContext, bars: list[dict[str, Any]]) -> None:
        if not bars:
            return
        params = ctx.params or {}
        phoenix: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        ok = phoenix.upsert_bars(
            asset_type=str(params["asset_type"]),
            market="zh_a",
            period=str(params["period"]),
            adjust="nf",
            bars=bars,
            run_id=ctx.run_id,
        )
        if not ok:
            ctx.fail(
                "failed to sink AmazingData K-line bars",
                phase="sink",
            )

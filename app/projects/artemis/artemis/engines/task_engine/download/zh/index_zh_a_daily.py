from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List

import AmazingData as ad
import pandas as pd

from artemis.consts import DeptServices, SDK_NAME
from artemis.core import TaskContext
from artemis.core.sdk.manager import sdk_mgr
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    incremental_start_date,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


class IndexZhADaily(WorkerUnit):
    """Download only configured A-share index bars using registered identities."""

    @staticmethod
    def _index_codes(params: Dict[str, Any]) -> List[str]:
        configured = params.get("indexes")
        if isinstance(configured, str):
            rows: List[Any] = [
                item.strip() for item in configured.split(",") if item.strip()
            ]
        elif isinstance(configured, (list, tuple, set)):
            rows = list(configured)
        else:
            rows = []

        result: List[str] = []
        for row in rows:
            code = (
                str(row).strip().upper()
                if isinstance(row, str)
                else str((row or {}).get("code", "")).strip().upper()
            )
            if "." not in code:
                continue
            symbol, exchange = code.rsplit(".", 1)
            if symbol and exchange in {"SH", "SZ", "BJ"}:
                result.append(f"{symbol}.{exchange}")
        return list(dict.fromkeys(result))

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        codes = self._index_codes(params)
        if not codes:
            ctx.fail(
                "INDEX_ZH_A_DAILY requires a non-empty indexes whitelist",
                phase="load_dynamic_parameters",
            )
            return

        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        symbols = [code.rsplit(".", 1)[0] for code in codes]
        registry = phoenix.get_securities(
            symbols=symbols,
            asset_type="index",
            market="zh_a",
            limit=max(len(codes) * 2, 100),
        )
        by_identity = {
            (row["symbol"], row["exchange"]): row
            for row in registry.values()
        }
        security_by_code: Dict[str, Dict[str, Any]] = {}
        missing: List[str] = []
        for code in codes:
            symbol, exchange = code.rsplit(".", 1)
            security = by_identity.get((symbol, exchange))
            if security is None:
                missing.append(code)
            else:
                security_by_code[code] = security
        if missing:
            ctx.fail(
                "index identities missing from security_registry; "
                f"run STOCK_ZH_A_LIST first: {missing}",
                phase="load_dynamic_parameters",
            )
            return

        last_updates = phoenix.get_bars_last_update(
            asset_type="index",
            market="zh_a",
            period="daily",
            adjust="nf",
            security_ids=[
                int(row["security_id"])
                for row in security_by_code.values()
            ],
        )
        effective_starts = {
            code: incremental_start_date(
                params.get("start_date"),
                last_updates.get(int(security["security_id"])),
                "2015-01-01",
            )
            for code, security in security_by_code.items()
        }
        end_date = date_string(params.get("end_date") or pd.Timestamp.now())
        ctx.params["index_codes"] = codes
        ctx.params["effective_start_dates"] = effective_starts
        ctx.params["pending_index_codes"] = [
            code for code in codes
            if effective_starts[code] <= end_date
        ]
        self._security_by_code = security_by_code

    def before_execute(self, ctx: TaskContext) -> None:
        if not (ctx.params or {}).get("pending_index_codes"):
            return
        try:
            base_data = sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
            self._market_data = ad.MarketData(base_data.get_calendar())
        except Exception as exc:
            ctx.fail(
                f"failed to acquire AmazingData market client: {exc}",
                phase="before_execute",
            )

    def execute(self, ctx: TaskContext):
        params = ctx.params or {}
        end_date = date_string(params.get("end_date") or pd.Timestamp.now())
        codes_by_start: Dict[str, List[str]] = defaultdict(list)
        for code in params["pending_index_codes"]:
            start_date = params["effective_start_dates"][code]
            codes_by_start[start_date].append(code)

        result: Dict[str, pd.DataFrame] = {}
        for start_date, codes in sorted(codes_by_start.items()):
            frames = self._market_data.query_kline(
                codes,
                begin_date=int(start_date.replace("-", "")),
                end_date=int(end_date.replace("-", "")),
                period=ad.constant.Period.day.value,
            )
            if isinstance(frames, dict):
                result.update(frames)
        return result

    @staticmethod
    def _frames(result: Any) -> Iterable[tuple[str, pd.DataFrame]]:
        if isinstance(result, dict):
            for code, frame in result.items():
                if isinstance(frame, pd.DataFrame):
                    yield str(code).upper(), frame

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        bars: List[Dict[str, Any]] = []
        rejected = 0
        security_by_code = getattr(self, "_security_by_code", {})
        effective_starts = (ctx.params or {}).get("effective_start_dates", {})
        end_date = date_string((ctx.params or {}).get("end_date") or pd.Timestamp.now())
        for code, frame in self._frames(result):
            security = security_by_code.get(code)
            if not security or frame.empty:
                continue
            start_date = effective_starts.get(code, "")
            work = frame.reset_index()
            date_col = "kline_time" if "kline_time" in work.columns else work.columns[0]
            for row in work.to_dict("records"):
                trade_date = pd.to_datetime(row.get(date_col), errors="coerce")
                trade_date_text = date_string(trade_date)
                required = {
                    key: pd.to_numeric(row.get(key), errors="coerce")
                    for key in ("open", "high", "low", "close")
                }
                if (
                    not trade_date_text
                    or trade_date_text < start_date
                    or trade_date_text > end_date
                    or any(pd.isna(value) for value in required.values())
                ):
                    rejected += 1
                    continue

                def optional_int(name: str):
                    value = pd.to_numeric(row.get(name), errors="coerce")
                    return None if pd.isna(value) else int(round(float(value)))

                bars.append({
                    "security_id": int(security["security_id"]),
                    "trade_date": trade_date_text,
                    "symbol": security["symbol"],
                    **{
                        key: round(float(value), 4)
                        for key, value in required.items()
                    },
                    "volume": optional_int("volume"),
                    "amount": optional_int("amount"),
                    "preclose": None,
                    "pct_chg": None,
                })
        ctx.logger.info({
            "event": "index_zh_a_daily_post_process",
            "run_id": ctx.run_id,
            "bars_count": len(bars),
            "rejected_count": rejected,
        })
        return bars

    def sink(self, ctx: TaskContext, bars: List[Dict[str, Any]]) -> None:
        if not bars:
            return
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        ok = phoenix.upsert_bars(
            asset_type="index",
            market="zh_a",
            period="daily",
            adjust="nf",
            source="amazing_data",
            bars=bars,
            run_id=ctx.run_id,
        )
        if not ok:
            ctx.fail(
                "failed to sink A-share core-index daily bars",
                phase="sink",
            )

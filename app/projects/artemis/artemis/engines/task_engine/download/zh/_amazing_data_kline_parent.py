from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit


class AmazingDataKlineParent(OrchestratorUnit):
    """Shared planner for asset-specific AmazingData K-line tasks."""

    ASSET_TYPE = ""
    CHILD_TASK_CODE: TaskCode
    SUPPORTED_PERIODS = {"min1", "min5", "min30", "daily"}

    # AmazingData currently truncates large responses at roughly 30,000 rows,
    # while Artemis child execution has a finite timeout. Keep each request
    # comfortably below both boundaries and split long backfills by date.
    ROWS_PER_TRADING_DAY = {
        "min1": 240,
        "min5": 48,
        "min30": 8,
        "daily": 1,
    }
    DEFAULT_MAX_ROWS_PER_CHILD = 12_000
    MAX_CALENDAR_DAYS_PER_CHILD = 120

    @staticmethod
    def _values(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [
                item.strip()
                for item in value.split(",")
                if item.strip()
            ]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _watermark_day(value: Any) -> str | None:
        text = str(value or "").strip()
        if len(text) < 10:
            return None
        candidate = text[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
        except ValueError:
            return None
        return candidate

    def parameter_check(self, ctx: TaskContext) -> None:
        params = ctx.incoming_params or {}
        asset_type = str(params.get("asset_type", "")).strip()
        period = str(params.get("period", "")).strip()
        if asset_type and asset_type != self.ASSET_TYPE:
            ctx.fail(
                f"{self.__class__.__name__} only accepts "
                f"asset_type={self.ASSET_TYPE}",
                phase="parameter_check",
            )
        if period and period not in self.SUPPORTED_PERIODS:
            ctx.fail(
                f"unsupported AmazingData period: {period}",
                phase="parameter_check",
            )

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        incoming_asset_type = str(params.get("asset_type", "")).strip()
        asset_type = self.ASSET_TYPE
        period = str(params.get("period", "")).strip()
        adjust = str(params.get("adjust", "nf")).strip()
        if not asset_type:
            ctx.fail(
                "asset-specific K-line task is missing ASSET_TYPE",
                phase="load_dynamic_parameters",
            )
            return
        if incoming_asset_type and incoming_asset_type != asset_type:
            ctx.fail(
                f"{self.__class__.__name__} only accepts "
                f"asset_type={asset_type}",
                phase="load_dynamic_parameters",
            )
            return
        if period not in self.SUPPORTED_PERIODS:
            ctx.fail(
                f"period must be one of {sorted(self.SUPPORTED_PERIODS)}",
                phase="load_dynamic_parameters",
            )
            return
        if adjust != "nf":
            ctx.fail(
                "AmazingData K-line task currently supports adjust=nf only",
                phase="load_dynamic_parameters",
            )
            return

        phoenix: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        raw_requested_ids = self._values(params.get("security_ids"))
        if any(
            not value.isdigit() or int(value) <= 0
            for value in raw_requested_ids
        ):
            ctx.fail(
                "security_ids must contain only positive integers",
                phase="load_dynamic_parameters",
            )
            return
        requested_ids = [int(value) for value in raw_requested_ids]
        requested_symbols = self._values(
            params.get("symbol_list") or params.get("symbols")
        )
        exchanges = [
            value.upper() for value in self._values(params.get("exchange"))
        ] or None

        start_date = str(params.get("start_date", "2021-01-01"))
        end_date = str(
            params.get("end_date") or datetime.now().strftime("%Y-%m-%d")
        )
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            ctx.fail(
                "start_date/end_date must be YYYY-MM-DD",
                phase="load_dynamic_parameters",
            )
            return
        if start > end:
            ctx.fail(
                "start_date must be <= end_date",
                phase="load_dynamic_parameters",
            )
            return

        securities: dict[int, dict[str, Any]] = {}
        if requested_ids:
            for security_id in requested_ids:
                info = phoenix.get_security_by_id(security_id)
                if info:
                    securities[security_id] = info
        elif requested_symbols:
            securities = phoenix.get_securities(
                symbols=requested_symbols,
                exchanges=exchanges,
                asset_type=asset_type,
                market="zh_a",
                limit=max(len(requested_symbols) * 3, 100),
            )
        elif bool(params.get("all_registered", False)):
            securities = phoenix.get_securities(
                exchanges=exchanges,
                asset_type=asset_type,
                market="zh_a",
                limit=20000,
            )
        else:
            ctx.fail(
                "on-demand AmazingData download requires security_ids/symbols; "
                "set all_registered=true explicitly for a full registry run",
                phase="load_dynamic_parameters",
            )
            return

        selected: dict[int, dict[str, Any]] = {}
        for security_id, info in securities.items():
            if (
                str(info.get("asset_type", asset_type)) == asset_type
                and str(info.get("market", "zh_a")) == "zh_a"
                and str(info.get("exchange", "")).upper() in {"SH", "SZ", "BJ"}
                and str(info.get("symbol", "")).strip()
            ):
                selected[int(security_id)] = info
        missing_ids = sorted(set(requested_ids).difference(selected))
        if missing_ids:
            ctx.fail(
                f"security_ids are missing or dimension-mismatched: {missing_ids}",
                phase="load_dynamic_parameters",
            )
            return
        found_symbols = {
            str(info.get("symbol", "")).strip()
            for info in selected.values()
        }
        missing_symbols = sorted(set(requested_symbols).difference(found_symbols))
        if missing_symbols:
            ctx.fail(
                "symbols are missing or dimension-mismatched in "
                f"security_registry: {missing_symbols}",
                phase="load_dynamic_parameters",
            )
            return
        if not selected:
            ctx.fail(
                "no matching securities found in security_registry",
                phase="load_dynamic_parameters",
            )
            return

        last_updates = phoenix.get_bars_last_update(
            asset_type=asset_type,
            market="zh_a",
            period=period,
            adjust="nf",
            security_ids=list(selected),
        )
        replay_from_start = str(params.get("replay_from_start", False)).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        effective_starts: dict[int, str] = {}
        for security_id in selected:
            watermark_day = (
                None
                if replay_from_start
                else self._watermark_day(last_updates.get(security_id))
            )
            effective_starts[security_id] = max(
                start_date,
                watermark_day or start_date,
            )

        ctx.params["asset_type"] = asset_type
        ctx.params["period"] = period
        ctx.params["adjust"] = "nf"
        ctx.params["end_date"] = end_date
        ctx.params["selected_securities"] = selected
        ctx.params["effective_start_dates"] = effective_starts

    @classmethod
    def _date_windows(
        cls,
        start_date: str,
        end_date: str,
        *,
        period: str,
        symbol_count: int,
        max_rows: int,
    ) -> list[tuple[str, str]]:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        rows_per_day = cls.ROWS_PER_TRADING_DAY[period]
        max_trading_days = max(
            1,
            max_rows // max(1, symbol_count * rows_per_day),
        )
        # Convert trading days to calendar days with a safety margin for the
        # provider row cap. The hard cap also prevents very long daily calls.
        calendar_days = max(1, int(max_trading_days * 7 / 5 * 0.9))
        calendar_days = min(calendar_days, cls.MAX_CALENDAR_DAYS_PER_CHILD)
        windows: list[tuple[str, str]] = []
        cursor = start
        while cursor <= end:
            window_end = min(end, cursor + timedelta(days=calendar_days - 1))
            windows.append((cursor.isoformat(), window_end.isoformat()))
            cursor = window_end + timedelta(days=1)
        return windows

    def plan(self, ctx: TaskContext) -> list[dict[str, Any]]:
        params = ctx.params or {}
        end_date = str(params["end_date"])
        selected = params.get("selected_securities", {}) or {}
        starts = params.get("effective_start_dates", {}) or {}
        batch_size = max(1, min(int(params.get("max_symbols_per_child", 50)), 200))
        max_rows = max(
            1_000,
            min(
                int(params.get("max_rows_per_child", self.DEFAULT_MAX_ROWS_PER_CHILD)),
                25_000,
            ),
        )

        by_start: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
        for raw_security_id, info in selected.items():
            security_id = int(raw_security_id)
            start_date = str(starts.get(security_id) or starts.get(str(security_id)))
            if start_date <= end_date:
                by_start[start_date].append((security_id, info))

        specs: list[dict[str, Any]] = []
        for start_date, rows in sorted(by_start.items()):
            for offset in range(0, len(rows), batch_size):
                batch = rows[offset : offset + batch_size]
                securities = {
                    f"{info['symbol']}.{str(info['exchange']).upper()}": {
                        "security_id": security_id,
                        "symbol": str(info["symbol"]),
                    }
                    for security_id, info in batch
                }
                windows = self._date_windows(
                    start_date,
                    end_date,
                    period=str(params["period"]),
                    symbol_count=len(batch),
                    max_rows=max_rows,
                )
                for window_start, window_end in windows:
                    specs.append(
                        {
                            "key": self.CHILD_TASK_CODE,
                            "params": {
                                "period": params["period"],
                                "adjust": "nf",
                                "start_date": window_start,
                                "end_date": window_end,
                                "securities": securities,
                            },
                        }
                    )
        ctx.logger.info(
            {
                "event": "zh_a_kline_parent_plan_complete",
                "run_id": ctx.run_id,
                "asset_type": params.get("asset_type"),
                "period": params.get("period"),
                "security_count": len(selected),
                "child_count": len(specs),
                "max_rows_per_child": max_rows,
            }
        )
        return specs

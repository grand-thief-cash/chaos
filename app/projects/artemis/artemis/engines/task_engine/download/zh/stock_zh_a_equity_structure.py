from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.zh.utils import (
    get_sdk_date_kwargs,
    get_security_map_for_task,
    normalize_date_yyyymmdd,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


_TOP_LEVEL_FIELDS = {
    "MARKET_CODE", "SECURITY_NAME", "ANN_DATE", "CHANGE_DATE",
    "CURRENT_SIGN", "IS_VALID",
}


class StockZHAEquityStructure(WorkerUnit):
    """Bounded AmazingData equity-structure history, defaulting to 2010.

    The paid SDK is queried in small security batches so a large production
    backfill can resume with ``symbol_offset`` rather than holding one giant
    request. PhoenixA's unique key makes retries idempotent.
    """

    def before_execute(self, ctx: TaskContext) -> None:
        from artemis.consts import SDK_NAME
        from artemis.core.sdk.manager import sdk_mgr

        try:
            sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
            self._info_data = ad.InfoData()
        except Exception as exc:
            ctx.fail(
                f"failed to acquire AmazingData SDK: {exc}",
                phase="before_execute",
            )

    def execute(self, ctx: TaskContext):
        from artemis.core.config_manager import cfg_mgr

        params = ctx.params or {}
        security_map = get_security_map_for_task(ctx)
        codes = sorted(security_map)
        offset = max(int(params.get("symbol_offset", 0)), 0)
        max_symbols = min(max(int(params.get("max_symbols_per_run", 20)), 1), 500)
        codes = codes[offset:offset + max_symbols]
        self._security_map = {code: security_map[code] for code in codes}
        if not codes:
            ctx.fail("no registered securities selected", phase="execute")
            return None

        cache_dir = os.path.abspath(
            cfg_mgr.task_engine_config().amazing_data_cache_dir,
        )
        os.makedirs(cache_dir, exist_ok=True)
        date_kwargs = get_sdk_date_kwargs(ctx)
        date_kwargs.setdefault("begin_date", 20100101)
        ctx.logger.info({
            "event": "equity_structure_execute_start",
            "code_count": len(codes),
            "symbol_offset": offset,
            "date_kwargs": date_kwargs,
            "run_id": ctx.run_id,
        })
        try:
            return self._info_data.get_equity_structure(
                codes,
                local_path=cache_dir,
                is_local=False,
                **date_kwargs,
            )
        except Exception as exc:
            ctx.fail(f"fetch equity structure failed: {exc}", phase="execute")
            return None

    @staticmethod
    def _frames(result: Any) -> Iterable[pd.DataFrame]:
        if isinstance(result, pd.DataFrame):
            return [result]
        if isinstance(result, dict):
            return [frame for frame in result.values() if isinstance(frame, pd.DataFrame)]
        return []

    @staticmethod
    def _flag(value: Any, default: int) -> int:
        parsed = pd.to_numeric(value, errors="coerce")
        return default if pd.isna(parsed) else int(parsed)

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        rows: Dict[tuple, Dict[str, Any]] = {}
        for frame in self._frames(result):
            for record in frame.to_dict("records"):
                market_code = str(record.get("MARKET_CODE") or "").strip()
                security = getattr(self, "_security_map", {}).get(market_code)
                change_date = normalize_date_yyyymmdd(
                    str(record.get("CHANGE_DATE") or ""),
                )
                if not security or not change_date:
                    continue
                ann_date = normalize_date_yyyymmdd(
                    str(record.get("ANN_DATE") or ""),
                )
                data_json: Dict[str, Any] = {}
                for key, value in record.items():
                    if key in _TOP_LEVEL_FIELDS or pd.isna(value):
                        continue
                    if hasattr(value, "item"):
                        value = value.item()
                    data_json[str(key)] = value
                row = {
                    "security_id": int(security["security_id"]),
                    "ann_date": ann_date,
                    "change_date": change_date,
                    "current_sign": self._flag(record.get("CURRENT_SIGN"), 0),
                    "is_valid": self._flag(record.get("IS_VALID"), 1),
                    "data_json": data_json,
                }
                key = (row["security_id"], change_date, ann_date)
                rows[key] = row
        result_rows = sorted(
            rows.values(), key=lambda row: (row["security_id"], row["change_date"]),
        )
        ctx.logger.info({
            "event": "equity_structure_post_process_done",
            "row_count": len(result_rows),
            "run_id": ctx.run_id,
        })
        return result_rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        source = consts.DataSource.DS_AMAZING_DATA.value
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        for start in range(0, len(rows), 500):
            if not phoenix.upsert_equity_structures(
                source=source,
                rows=rows[start:start + 500],
                run_id=ctx.run_id,
            ):
                ctx.fail("failed to sink equity structure", phase="sink")
                return

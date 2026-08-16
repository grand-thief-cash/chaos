from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import AmazingData as ad
import pandas as pd

from artemis.consts import DeptServices, SDK_NAME
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.core.sdk.manager import sdk_mgr
from artemis.engines.task_engine.worker_unit import WorkerUnit


class StockZhALevel1File(WorkerUnit):
    """Download a small Level-1 research pilot into partitioned Parquet files.

    This task intentionally does not call PhoenixA. The files are an
    experimental dataset and must demonstrate out-of-sample value before a
    database contract or retention policy is introduced.
    """

    MANIFEST_SCHEMA_VERSION = 1
    HARD_MAX_SECURITIES = 10
    HARD_MAX_CALENDAR_DAYS = 31

    @staticmethod
    def _values(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @classmethod
    def _partition_complete(cls, partition: Path) -> bool:
        manifest_path = partition / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        if (
            manifest.get("schema_version") != cls.MANIFEST_SCHEMA_VERSION
            or manifest.get("status") != "complete"
        ):
            return False
        if int(manifest.get("row_count", -1)) == 0:
            return True
        data_path = partition / str(manifest.get("data_file", "snapshot.parquet"))
        try:
            expected_size = int(manifest["byte_size"])
            expected_sha256 = str(manifest["sha256"])
        except (KeyError, TypeError, ValueError):
            return False
        return (
            data_path.is_file()
            and data_path.stat().st_size == expected_size
            and cls._sha256(data_path) == expected_sha256
        )

    def parameter_check(self, ctx: TaskContext) -> None:
        incoming = ctx.incoming_params or {}
        if self._as_bool(incoming.get("all_registered")):
            ctx.fail(
                "Level-1 file pilot forbids all_registered; select at most 10 securities",
                phase="parameter_check",
            )

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        raw_ids = self._values(params.get("security_ids"))
        if any(not value.isdigit() or int(value) <= 0 for value in raw_ids):
            ctx.fail("security_ids must contain positive integers", phase="load_dynamic_parameters")
            return
        requested_ids = [int(value) for value in raw_ids]
        requested_symbols = [
            value.split(".", 1)[0]
            for value in self._values(params.get("symbols") or params.get("symbol_list"))
        ]
        if not requested_ids and not requested_symbols:
            ctx.fail("security_ids or symbols are required", phase="load_dynamic_parameters")
            return

        max_securities = min(
            self.HARD_MAX_SECURITIES,
            max(1, int(params.get("max_securities", self.HARD_MAX_SECURITIES))),
        )
        requested_count = len(set(requested_ids)) + len(set(requested_symbols))
        if requested_count > max_securities:
            ctx.fail(
                f"Level-1 file pilot accepts at most {max_securities} securities",
                phase="load_dynamic_parameters",
            )
            return

        phoenix: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        selected: dict[int, dict[str, Any]] = {}
        if requested_ids:
            for security_id in requested_ids:
                info = phoenix.get_security_by_id(security_id)
                if info:
                    selected[security_id] = info
        if requested_symbols:
            selected.update(
                phoenix.get_securities(
                    symbols=requested_symbols,
                    asset_type="stock",
                    market="zh_a",
                    limit=max(100, len(requested_symbols) * 3),
                )
            )
        selected = {
            int(security_id): info
            for security_id, info in selected.items()
            if str(info.get("asset_type", "")) == "stock"
            and str(info.get("market", "")) == "zh_a"
            and str(info.get("exchange", "")).upper() in {"SH", "SZ", "BJ"}
            and str(info.get("symbol", "")).strip()
        }
        if len(selected) != requested_count:
            ctx.fail(
                "one or more requested securities are missing or not active A-share stocks",
                phase="load_dynamic_parameters",
            )
            return

        start_text = str(params.get("start_date") or datetime.now().strftime("%Y-%m-%d"))
        end_text = str(params.get("end_date") or start_text)
        try:
            start = date.fromisoformat(start_text)
            end = date.fromisoformat(end_text)
        except ValueError:
            ctx.fail("start_date/end_date must be YYYY-MM-DD", phase="load_dynamic_parameters")
            return
        max_days = min(
            self.HARD_MAX_CALENDAR_DAYS,
            max(1, int(params.get("max_calendar_days", self.HARD_MAX_CALENDAR_DAYS))),
        )
        if start > end or (end - start).days + 1 > max_days:
            ctx.fail(
                f"date range must contain 1..{max_days} calendar days",
                phase="load_dynamic_parameters",
            )
            return

        raw_root = Path(str(params.get("storage_root") or "runtime/artemis/level1_snapshot"))
        storage_root = (Path.cwd() / raw_root).resolve() if not raw_root.is_absolute() else raw_root.resolve()
        forbidden = {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}
        if storage_root in forbidden:
            ctx.fail("storage_root is too broad", phase="load_dynamic_parameters")
            return

        ctx.params["selected_securities"] = selected
        ctx.params["start_date"] = start.isoformat()
        ctx.params["end_date"] = end.isoformat()
        ctx.params["storage_root"] = str(storage_root)
        ctx.params["force"] = self._as_bool(params.get("force"))

    def before_execute(self, ctx: TaskContext) -> None:
        try:
            base_data = sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
            self._market_data = ad.MarketData(base_data.get_calendar())
        except Exception as exc:
            ctx.fail(
                f"failed to acquire AmazingData market client: {exc}",
                phase="before_execute",
            )

    @staticmethod
    def _frame_for_code(
        result: Any,
        vendor_code: str,
        symbol: str,
        *,
        allow_unscoped: bool = False,
    ) -> pd.DataFrame:
        if not isinstance(result, dict):
            return pd.DataFrame()
        expected = vendor_code.upper()
        stack: list[tuple[tuple[str, ...], Any]] = [((), result)]
        frames: list[tuple[tuple[str, ...], pd.DataFrame]] = []
        while stack:
            path, value = stack.pop()
            if isinstance(value, pd.DataFrame):
                frames.append((path, value))
            elif isinstance(value, dict):
                stack.extend(
                    (path + (str(key),), nested)
                    for key, nested in value.items()
                )
        for path, frame in frames:
            path_text = "|".join(path)
            if expected in path_text.upper():
                return frame
            symbols = re.findall(r"(?<!\d)\d{6}(?!\d)", path_text)
            if symbol in symbols:
                return frame
        for _, frame in frames:
            for column in frame.columns:
                values = frame[column].astype(str)
                matches = values.str.contains(
                    rf"(?<!\d){re.escape(symbol)}(?!\d)", regex=True, na=False
                )
                if matches.any():
                    return frame.loc[matches].copy()
            index_values = pd.Series(frame.index.astype(str), index=frame.index)
            matches = index_values.str.contains(
                rf"(?<!\d){re.escape(symbol)}(?!\d)", regex=True, na=False
            )
            if matches.any():
                return frame.loc[matches.to_numpy()].copy()
        if allow_unscoped and len(frames) == 1:
            return frames[0][1]
        return pd.DataFrame()

    def execute(self, ctx: TaskContext) -> Iterator[dict[str, Any]]:
        params = ctx.params or {}
        selected = params.get("selected_securities", {}) or {}
        root = Path(str(params["storage_root"]))
        force = bool(params.get("force"))
        cursor = date.fromisoformat(str(params["start_date"]))
        end = date.fromisoformat(str(params["end_date"]))

        while cursor <= end:
            trade_date = cursor.isoformat()
            pending: dict[str, dict[str, Any]] = {}
            for security_id, info in selected.items():
                partition = root / f"security_id={int(security_id)}" / f"trade_date={trade_date}"
                if force or not self._partition_complete(partition):
                    code = f"{info['symbol']}.{str(info['exchange']).upper()}"
                    pending[code] = {**info, "security_id": int(security_id)}
            if pending:
                result = self._market_data.query_snapshot(
                    list(pending),
                    begin_date=int(trade_date.replace("-", "")),
                    end_date=int(trade_date.replace("-", "")),
                )
                ctx.logger.info(
                    {
                        "event": "stock_zh_a_level1_file_query",
                        "run_id": ctx.run_id,
                        "trade_date": trade_date,
                        "requested_codes": list(pending),
                        "result_type": type(result).__name__,
                        "result_keys": (
                            [str(key) for key in list(result)[:10]]
                            if isinstance(result, dict)
                            else []
                        ),
                        "result_values": (
                            [
                                {
                                    "key": str(key),
                                    "type": type(value).__name__,
                                    "rows": len(value) if isinstance(value, pd.DataFrame) else None,
                                    "columns": (
                                        [str(column) for column in value.columns[:20]]
                                        if isinstance(value, pd.DataFrame)
                                        else []
                                    ),
                                    "nested_keys": (
                                        [str(item) for item in list(value)[:10]]
                                        if isinstance(value, dict)
                                        else []
                                    ),
                                }
                                for key, value in list(result.items())[:10]
                            ]
                            if isinstance(result, dict)
                            else []
                        ),
                    }
                )
                for code, info in pending.items():
                    frame = self._frame_for_code(
                        result,
                        code,
                        str(info["symbol"]),
                        allow_unscoped=len(pending) == 1,
                    )
                    yield {
                        "vendor_code": code.upper(),
                        "security": info,
                        "trade_date": trade_date,
                        "frame": frame,
                    }
            cursor += timedelta(days=1)

    @staticmethod
    def _time_statistics(work: pd.DataFrame) -> dict[str, Any]:
        lowered = {str(column).lower(): column for column in work.columns}
        time_column = next(
            (
                lowered[name]
                for name in ("trade_time", "snapshot_time", "datetime", "timestamp", "vendor_index")
                if name in lowered
            ),
            None,
        )
        if time_column is None:
            return {"time_column": None, "min_time": None, "max_time": None}
        parsed = pd.to_datetime(work[time_column], errors="coerce").dropna().sort_values()
        if parsed.empty:
            return {"time_column": str(time_column), "min_time": None, "max_time": None}
        deltas = parsed.diff().dt.total_seconds().dropna()
        return {
            "time_column": str(time_column),
            "min_time": parsed.iloc[0].isoformat(),
            "max_time": parsed.iloc[-1].isoformat(),
            "duplicate_time_count": int(parsed.duplicated().sum()),
            "median_cadence_seconds": None if deltas.empty else float(deltas.median()),
            "p95_cadence_seconds": None if deltas.empty else float(deltas.quantile(0.95)),
            "max_cadence_seconds": None if deltas.empty else float(deltas.max()),
        }

    def _write_partition(self, ctx: TaskContext, item: dict[str, Any]) -> str:
        params = ctx.params or {}
        info = item["security"]
        security_id = int(info["security_id"])
        trade_date = str(item["trade_date"])
        partition = (
            Path(str(params["storage_root"]))
            / f"security_id={security_id}"
            / f"trade_date={trade_date}"
        )
        frame: pd.DataFrame = item["frame"]
        if frame.empty and bool(params.get("force")) and self._partition_complete(partition):
            return "preserved"

        partition.mkdir(parents=True, exist_ok=True)
        manifest_path = partition / "manifest.json"
        data_path = partition / "snapshot.parquet"
        completed_at = datetime.now().astimezone().isoformat(timespec="seconds")
        if frame.empty:
            manifest = {
                "schema_version": self.MANIFEST_SCHEMA_VERSION,
                "status": "complete",
                "source": "amazing_data",
                "security_id": security_id,
                "symbol": str(info["symbol"]),
                "exchange": str(info["exchange"]).upper(),
                "vendor_code": str(item["vendor_code"]),
                "trade_date": trade_date,
                "row_count": 0,
                "data_file": None,
                "byte_size": 0,
                "sha256": None,
                "completed_at": completed_at,
            }
        else:
            index_name = "vendor_index"
            while index_name in frame.columns:
                index_name = "_" + index_name
            work = frame.reset_index(names=index_name)
            work.insert(0, "meta_vendor_code", str(item["vendor_code"]))
            work.insert(0, "meta_exchange", str(info["exchange"]).upper())
            work.insert(0, "meta_symbol", str(info["symbol"]))
            work.insert(0, "meta_security_id", security_id)
            work.insert(0, "meta_trade_date", trade_date)

            handle, temp_name = tempfile.mkstemp(
                prefix="snapshot-",
                suffix=".parquet.tmp",
                dir=partition,
            )
            os.close(handle)
            temp_path = Path(temp_name)
            try:
                work.to_parquet(temp_path, index=False, compression="zstd")
                os.replace(temp_path, data_path)
            finally:
                if temp_path.exists():
                    temp_path.unlink()
            manifest = {
                "schema_version": self.MANIFEST_SCHEMA_VERSION,
                "status": "complete",
                "source": "amazing_data",
                "security_id": security_id,
                "symbol": str(info["symbol"]),
                "exchange": str(info["exchange"]).upper(),
                "vendor_code": str(item["vendor_code"]),
                "trade_date": trade_date,
                "row_count": int(len(work)),
                "data_file": data_path.name,
                "byte_size": data_path.stat().st_size,
                "sha256": self._sha256(data_path),
                "columns": [str(column) for column in work.columns],
                "dtypes": {str(column): str(dtype) for column, dtype in work.dtypes.items()},
                "completed_at": completed_at,
                **self._time_statistics(work),
            }

        handle, temp_name = tempfile.mkstemp(
            prefix="manifest-",
            suffix=".json.tmp",
            dir=partition,
        )
        os.close(handle)
        temp_path = Path(temp_name)
        try:
            temp_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            os.replace(temp_path, manifest_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return "empty" if frame.empty else "written"

    def sink(self, ctx: TaskContext, partitions: Iterator[dict[str, Any]]) -> None:
        counts = {"written": 0, "empty": 0, "preserved": 0}
        for item in partitions:
            counts[self._write_partition(ctx, item)] += 1
        ctx.stats.update(
            {
                "storage_mode": "partitioned_parquet",
                "storage_root": str((ctx.params or {}).get("storage_root")),
                **{f"partition_{key}": value for key, value in counts.items()},
            }
        )
        ctx.logger.info(
            {
                "event": "stock_zh_a_level1_file_complete",
                "run_id": ctx.run_id,
                **counts,
            }
        )

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.risk_download_utils import (
    rate_limited_call,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit
from .series import RATE_SERIES


SOURCE_SPECS = {
    "index": {
        "api": "index_global_spot_em",
        "asset_type": "index",
        "exchange": "GLOBAL",
    },
    "fx": {
        "api": "forex_spot_em",
        "asset_type": "fx",
        "exchange": "FX",
    },
    "futures": {
        "api": "futures_global_spot_em",
        "asset_type": "futures",
        "exchange": "GLOBAL",
    },
}

GLOBAL_INDEX_EXCHANGES = {
    "SPX": "US",
    "NDX": "US",
    "DJIA": "US",
    "UDI": "US",
    "HSI": "HK",
    "HSCEI": "HK",
    "KS11": "KR",
    "KOSPI200": "KR",
    "TWII": "TW",
    "N225": "JP",
}


def _string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return []


class GlobalSecurityList(WorkerUnit):
    """Refresh global index, FX, futures and macro-series identities."""

    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        sources = _string_list((ctx.params or {}).get("sources"))
        unsupported = [
            source
            for source in sources
            if source not in {*SOURCE_SPECS, "rate"}
        ]
        if not sources or unsupported:
            ctx.fail(
                f"sources are required; unsupported={unsupported}",
                phase="execute",
            )
            return {}
        result: Dict[str, Any] = {}
        for source in sources:
            if source == "rate":
                result[source] = RATE_SERIES
                continue
            source_spec = SOURCE_SPECS[source]
            downloader = getattr(ak, source_spec["api"])
            result[source] = rate_limited_call(
                ctx,
                source_spec["api"],
                downloader,
            )
        result["manual"] = (ctx.params or {}).get("manual_securities") or []
        return result

    @staticmethod
    def _snapshot_rows(source: str, value: Any) -> Iterable[Dict[str, Any]]:
        if source == "rate":
            for spec in value:
                yield {
                    "symbol": spec["symbol"],
                    "name": spec["name"],
                    "exchange": spec["exchange"],
                    "asset_type": "macro",
                    "market": "global",
                    "status": "active",
                }
            return
        source_spec = SOURCE_SPECS.get(source)
        if source_spec is None or not isinstance(value, pd.DataFrame):
            return
        for record in value.to_dict("records"):
            symbol = str(record.get("代码") or "").strip().upper()
            name = str(record.get("名称") or "").strip()
            if not symbol or not name:
                continue
            yield {
                "symbol": symbol,
                "name": name,
                "exchange": (
                    GLOBAL_INDEX_EXCHANGES.get(
                        symbol,
                        source_spec["exchange"],
                    )
                    if source == "index"
                    else source_spec["exchange"]
                ),
                "asset_type": source_spec["asset_type"],
                "market": "global",
                "status": "active",
            }

    def post_process(
        self,
        ctx: TaskContext,
        result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for source, value in result.items():
            if source == "manual":
                for raw in value if isinstance(value, list) else []:
                    if not isinstance(raw, dict):
                        continue
                    row = {
                        "symbol": str(raw.get("symbol") or "").strip().upper(),
                        "name": str(raw.get("name") or "").strip(),
                        "exchange": str(raw.get("exchange") or "GLOBAL").strip().upper(),
                        "asset_type": str(raw.get("asset_type") or "").strip(),
                        "market": str(raw.get("market") or "global").strip(),
                        "status": str(raw.get("status") or "active").strip(),
                    }
                    if row["symbol"] and row["name"] and row["asset_type"]:
                        rows.append(row)
                continue
            rows.extend(self._snapshot_rows(source, value))
        deduplicated = {
            (row["exchange"], row["asset_type"], row["symbol"]): row
            for row in rows
        }
        return sorted(
            deduplicated.values(),
            key=lambda row: (
                row["asset_type"], row["exchange"], row["symbol"],
            ),
        )

    @staticmethod
    def _changed_rows(
        downloaded: List[Dict[str, Any]],
        existing: Dict[tuple[str, str], Dict[tuple[str, str], Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        changed: List[Dict[str, Any]] = []
        for row in downloaded:
            current = existing.get(
                (row["asset_type"], row["market"]),
                {},
            ).get((row["exchange"], row["symbol"]))
            if current is None or any(
                str(current.get(field, "")) != str(row[field])
                for field in ("name", "status")
            ):
                changed.append(row)
        return changed

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        ctx.stats["downloaded_identity_count"] = len(rows)
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        existing: Dict[
            tuple[str, str],
            Dict[tuple[str, str], Dict[str, Any]],
        ] = {}
        for asset_type, market in {
            (row["asset_type"], row["market"])
            for row in rows
        }:
            registry = phoenix.get_securities(
                asset_type=asset_type,
                market=market,
                limit=20000,
            )
            existing[(asset_type, market)] = {
                (row["exchange"], row["symbol"]): row
                for row in registry.values()
            }
        changed = self._changed_rows(rows, existing)
        ctx.stats["changed_identity_count"] = len(changed)
        if changed and not phoenix.upsert_securities(
            changed,
            run_id=ctx.run_id,
        ):
            ctx.fail(
                "failed to incrementally update global security registry",
                phase="sink",
            )

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pandas as pd

from artemis.consts import DeptServices, SDK_NAME
from artemis.core import TaskContext
from artemis.core.sdk.manager import sdk_mgr
from artemis.engines.task_engine.worker_unit import WorkerUnit


# AmazingData development guide §3.5.2 / §4.1. The four core spot
# instrument types are enabled by default in task.yaml. The remaining types are
# supported explicitly and can be enabled without changing task code.
SECURITY_TYPE_SPECS: Dict[str, Dict[str, str]] = {
    "stock": {
        "api": "get_code_info",
        "security_type": "EXTRA_STOCK_A",
        "asset_type": "stock",
        "market": "zh_a",
    },
    "index": {
        "api": "get_code_info",
        "security_type": "EXTRA_INDEX_A",
        "asset_type": "index",
        "market": "zh_a",
    },
    "etf": {
        "api": "get_code_info",
        "security_type": "EXTRA_ETF",
        "asset_type": "etf",
        "market": "zh_a",
    },
    "cb": {
        "api": "get_code_info",
        "security_type": "EXTRA_KZZ",
        "asset_type": "cb",
        "market": "zh_a",
    },
    "hk_connect": {
        "api": "get_code_info",
        "security_type": "EXTRA_HKT",
        "asset_type": "stock",
        "market": "hk_connect",
    },
    "repo": {
        "api": "get_code_info",
        "security_type": "EXTRA_GLRA",
        "asset_type": "repo",
        "market": "zh_a",
    },
    "futures": {
        "api": "get_future_code_list",
        "security_type": "EXTRA_FUTURE",
        "asset_type": "futures",
        "market": "zh_futures",
        "default_exchange": "CFE",
    },
    "option": {
        "api": "get_option_code_list",
        "security_type": "EXTRA_ETF_OP",
        "asset_type": "option",
        "market": "zh_option",
    },
}

DEFAULT_SECURITY_TYPES = ("stock", "index", "etf", "cb")
VALID_EXCHANGES = {"SH", "SZ", "BJ", "SHN", "SZN", "CFE", "ALL"}


def _string_list(value: Any, default: Iterable[str]) -> List[str]:
    if isinstance(value, str):
        values = [item.strip().lower() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        values = []
    return list(dict.fromkeys(values or default))


def _split_code(code: Any, default_exchange: str = "") -> tuple[str, str]:
    text = str(code or "").strip().upper()
    if not text:
        return "", ""
    if "." in text:
        symbol, exchange = text.rsplit(".", 1)
        return symbol.strip(), exchange.strip()
    return text, default_exchange


class StockZHAList(WorkerUnit):
    """Refresh the unified Chinese security registry from AmazingData.

    AmazingData's code-list endpoints are current snapshots and do not expose a
    server-side change cursor. The task therefore downloads the selected small
    identity snapshots, compares them with PhoenixA, and upserts only new or
    changed identities. Existing IDs are never recreated.
    """

    def parameter_check(self, ctx: TaskContext) -> None:
        params = ctx.incoming_params or {}
        exchange = str(params.get("exchange") or "ALL").strip().upper()
        if exchange not in VALID_EXCHANGES:
            ctx.fail(
                f"invalid exchange: {exchange}, expected one of {sorted(VALID_EXCHANGES)}",
                phase="parameter_check",
            )
            return
        requested = _string_list(
            params.get("security_types"),
            DEFAULT_SECURITY_TYPES,
        )
        unsupported = [item for item in requested if item not in SECURITY_TYPE_SPECS]
        if unsupported:
            ctx.fail(
                f"unsupported security_types: {unsupported}",
                phase="parameter_check",
            )

    def before_execute(self, ctx: TaskContext) -> None:
        try:
            self._base_data = sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
        except Exception as exc:
            ctx.fail(
                f"failed to acquire AmazingData SDK: {exc}",
                phase="before_execute",
            )

    @staticmethod
    def _rows_from_code_info(
        frame: Any,
        spec: Dict[str, str],
        exchange_filter: str,
    ) -> List[Dict[str, Any]]:
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return []
        work = frame.reset_index()
        code_column = work.columns[0]
        rows: List[Dict[str, Any]] = []
        for record in work.to_dict("records"):
            symbol, exchange = _split_code(
                record.get(code_column),
                spec.get("default_exchange", ""),
            )
            if (
                not symbol
                or not exchange
                or (exchange_filter != "ALL" and exchange != exchange_filter)
            ):
                continue
            name = str(record.get("symbol") or symbol).strip()
            rows.append({
                "symbol": symbol,
                "name": name,
                "exchange": exchange,
                "asset_type": spec["asset_type"],
                "market": spec["market"],
                "status": "active",
            })
        return rows

    @staticmethod
    def _rows_from_code_list(
        codes: Any,
        spec: Dict[str, str],
        exchange_filter: str,
    ) -> List[Dict[str, Any]]:
        if not isinstance(codes, (list, tuple, set)):
            return []
        rows: List[Dict[str, Any]] = []
        for code in codes:
            symbol, exchange = _split_code(
                code,
                spec.get("default_exchange", ""),
            )
            if (
                not symbol
                or not exchange
                or (exchange_filter != "ALL" and exchange != exchange_filter)
            ):
                continue
            rows.append({
                "symbol": symbol,
                "name": symbol,
                "exchange": exchange,
                "asset_type": spec["asset_type"],
                "market": spec["market"],
                "status": "active",
            })
        return rows

    def execute(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        params = ctx.params or {}
        exchange_filter = str(params.get("exchange") or "ALL").strip().upper()
        requested = _string_list(
            params.get("security_types"),
            DEFAULT_SECURITY_TYPES,
        )
        rows: List[Dict[str, Any]] = []
        for logical_type in requested:
            spec = SECURITY_TYPE_SPECS[logical_type]
            downloader = getattr(self._base_data, spec["api"])
            result = downloader(security_type=spec["security_type"])
            if spec["api"] == "get_code_info":
                normalized = self._rows_from_code_info(
                    result,
                    spec,
                    exchange_filter,
                )
            else:
                normalized = self._rows_from_code_list(
                    result,
                    spec,
                    exchange_filter,
                )
            rows.extend(normalized)
            ctx.logger.info({
                "event": "security_registry_source_snapshot",
                "logical_type": logical_type,
                "security_type": spec["security_type"],
                "row_count": len(normalized),
                "run_id": ctx.run_id,
            })

        # Guard against an SDK snapshot containing duplicate identities.
        deduplicated = {
            (row["exchange"], row["asset_type"], row["symbol"]): row
            for row in rows
        }
        result = list(deduplicated.values())
        result.sort(
            key=lambda row: (
                row["market"], row["asset_type"], row["exchange"], row["symbol"],
            ),
        )
        return result

    @staticmethod
    def _changed_rows(
        downloaded: List[Dict[str, Any]],
        existing_by_scope: Dict[tuple[str, str], Dict[tuple[str, str], Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        changed: List[Dict[str, Any]] = []
        for row in downloaded:
            scope = (row["asset_type"], row["market"])
            key = (row["exchange"], row["symbol"])
            current = existing_by_scope.get(scope, {}).get(key)
            if current is None:
                changed.append(row)
                continue
            if any(
                str(current.get(field, "")) != str(row.get(field, ""))
                for field in ("name", "status")
            ):
                changed.append(row)
        return changed

    def sink(self, ctx: TaskContext, downloaded: List[Dict[str, Any]]) -> None:
        ctx.stats["downloaded_identity_count"] = len(downloaded)
        if not downloaded:
            ctx.stats["changed_identity_count"] = 0
            return

        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        existing_by_scope: Dict[
            tuple[str, str],
            Dict[tuple[str, str], Dict[str, Any]],
        ] = {}
        scopes = {
            (row["asset_type"], row["market"])
            for row in downloaded
        }
        for asset_type, market in scopes:
            existing = phoenix.get_securities(
                asset_type=asset_type,
                market=market,
                limit=20000,
            )
            existing_by_scope[(asset_type, market)] = {
                (row["exchange"], row["symbol"]): row
                for row in existing.values()
            }

        changed = self._changed_rows(downloaded, existing_by_scope)
        ctx.stats["changed_identity_count"] = len(changed)
        if not changed:
            ctx.logger.info({
                "event": "security_registry_incremental_skip",
                "downloaded_count": len(downloaded),
                "run_id": ctx.run_id,
            })
            return
        if not phoenix.upsert_securities(changed, run_id=ctx.run_id):
            ctx.fail("failed to incrementally update security registry", phase="sink")
            return
        ctx.logger.info({
            "event": "security_registry_incremental_upsert",
            "downloaded_count": len(downloaded),
            "changed_count": len(changed),
            "run_id": ctx.run_id,
        })

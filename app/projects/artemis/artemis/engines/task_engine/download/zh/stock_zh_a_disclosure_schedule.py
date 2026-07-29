from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    rate_limited_call,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


REPORT_TYPES = ("一季", "半年报", "三季", "年报")
PERIOD_PATTERN = re.compile(r"^\d{4}(?:一季|半年报|三季|年报)$")


def _list_param(value: Any) -> List[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def disclosure_periods(
    params: Dict[str, Any],
    now: pd.Timestamp | None = None,
) -> List[str]:
    """Resolve explicit or currently active CNInfo reporting periods."""
    explicit = _list_param(params.get("periods"))
    if explicit:
        return list(dict.fromkeys(
            period for period in explicit
            if PERIOD_PATTERN.fullmatch(period)
        ))

    current = (now or pd.Timestamp.now()).normalize()
    year = int(params.get("year") or current.year)
    report_types = _list_param(params.get("report_types"))
    if report_types:
        return [
            f"{year}{report_type}"
            for report_type in dict.fromkeys(report_types)
            if report_type in REPORT_TYPES
        ]

    # CNInfo only exposes the most recent four periods. Query the currently
    # active appointment window rather than repeatedly requesting fixed history.
    month = current.month
    if month <= 2:
        return [f"{current.year - 1}年报"]
    if month <= 4:
        return [f"{current.year - 1}年报", f"{current.year}一季"]
    if month <= 7:
        return [f"{current.year}半年报"]
    if month <= 10:
        return [f"{current.year}三季"]
    return [f"{current.year}年报"]


def _canonical_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return json.dumps(
        value or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class StockZhADisclosureSchedule(WorkerUnit):
    """Incremental CNInfo financial-report appointment snapshots."""

    def execute(self, ctx: TaskContext):
        params = ctx.params or {}
        periods = disclosure_periods(params)
        if not periods:
            ctx.fail(
                "no valid disclosure periods resolved",
                phase="execute",
            )
            return {}

        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        registry = phoenix.get_securities(
            asset_type="stock",
            market="zh_a",
            limit=20000,
        )
        self._security_by_symbol = {
            row["symbol"]: row
            for row in registry.values()
        }
        self._existing_events: Dict[
            tuple[int, str, str],
            str,
        ] = {}
        for period in periods:
            title = f"{period}披露计划"
            existing = phoenix.get_security_events(
                source="cninfo",
                event_type="disclosure_schedule",
                title=title,
            )
            for row in existing:
                key = (
                    int(row.get("security_id") or 0),
                    date_string(row.get("event_date")),
                    str(row.get("title") or ""),
                )
                if key[0] and key[1] and key[2]:
                    self._existing_events[key] = _canonical_json(
                        row.get("data_json"),
                    )

        return {
            period: rate_limited_call(
                ctx,
                f"stock_report_disclosure:{period}",
                lambda period=period: ak.stock_report_disclosure(
                    market="沪深京",
                    period=period,
                ),
            )
            for period in periods
        }

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not isinstance(result, dict):
            return events
        security_by_symbol = getattr(self, "_security_by_symbol", {})
        existing_events = getattr(self, "_existing_events", {})
        date_fields = ["首次预约", "初次变更", "二次变更", "三次变更", "实际披露"]
        seen: set[tuple[int, str, str]] = set()
        for period, frame in result.items():
            if not isinstance(frame, pd.DataFrame):
                continue
            for record in frame.to_dict("records"):
                symbol = str(record.get("股票代码", "")).strip().zfill(6)
                security = security_by_symbol.get(symbol)
                dates = {
                    field: date_string(record.get(field))
                    for field in date_fields
                }
                current_date = next(
                    (
                        dates[field]
                        for field in reversed(date_fields)
                        if dates[field]
                    ),
                    "",
                )
                if not security or not current_date:
                    continue
                title = f"{period}披露计划"
                data_json = {
                    "symbol": symbol,
                    "security_name": str(
                        record.get("股票简称", ""),
                    ).strip(),
                    "reporting_period": period,
                    **dates,
                }
                key = (
                    int(security["security_id"]),
                    current_date,
                    title,
                )
                if key in seen:
                    continue
                seen.add(key)
                if existing_events.get(key) == _canonical_json(data_json):
                    continue
                events.append({
                    "security_id": key[0],
                    "event_date": current_date,
                    "title": title,
                    "url": "",
                    "data_json": data_json,
                })
        ctx.logger.info({
            "event": "stock_zh_a_disclosure_schedule_delta",
            "delta_count": len(events),
            "periods": list(result),
            "run_id": ctx.run_id,
        })
        return events

    def sink(self, ctx: TaskContext, events: List[Dict[str, Any]]) -> None:
        if not events:
            return
        ok = ctx.dept_http[DeptServices.PHOENIXA].upsert_security_events(
            source="cninfo",
            event_type="disclosure_schedule",
            rows=events,
            run_id=ctx.run_id,
        )
        if not ok:
            ctx.fail(
                "failed to sink CNInfo disclosure schedules",
                phase="sink",
            )

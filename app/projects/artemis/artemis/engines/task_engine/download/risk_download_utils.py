from __future__ import annotations

import time
from datetime import timedelta
from typing import Any, Dict

import pandas as pd

from artemis.core import TaskContext


def optional_number(value: Any) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) else float(parsed)


def date_string(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def within_date_range(date: str, params: Dict[str, Any]) -> bool:
    start = start_date_for_run(params, "")
    end = str(params.get("end_date") or "")
    return bool(date) and (not start or date >= start) and (not end or date <= end)


def start_date_for_run(params: Dict[str, Any], default: str) -> str:
    if str(params.get("mode", "")).lower() == "incremental":
        lookback_days = max(int(params.get("lookback_days", 10)), 1)
        return (pd.Timestamp.now().normalize() - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    return str(params.get("start_date") or default)


def incremental_start_date(
    configured_start: Any,
    last_update: Any,
    default: str,
) -> str:
    """Return max(configured/default start, last persisted date + one day)."""
    base = date_string(configured_start or default)
    latest = pd.to_datetime(last_update, errors="coerce")
    if pd.isna(latest):
        return base
    next_date = (latest + timedelta(days=1)).strftime("%Y-%m-%d")
    return max(base, next_date) if base else next_date


def rate_limited_call(ctx: TaskContext, label: str, func):
    seconds = max(float((ctx.params or {}).get("request_interval_seconds", 1.5)), 0.0)
    try:
        return func()
    except Exception as exc:
        ctx.logger.warning({
            "event": "risk_download_source_call_failed",
            "label": label,
            "error": str(exc),
            "run_id": ctx.run_id,
        })
        return None
    finally:
        if seconds:
            time.sleep(seconds)

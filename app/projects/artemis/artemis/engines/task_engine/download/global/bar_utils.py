from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List

import pandas as pd

from artemis.consts import DeptServices
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    incremental_start_date,
)


def configured_specs(params: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = params.get(key)
    if not isinstance(value, (list, tuple)):
        return []
    result: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            spec = {"symbol": item.strip().upper()}
        elif isinstance(item, dict):
            spec = dict(item)
            spec["symbol"] = str(spec.get("symbol", "")).strip().upper()
        else:
            continue
        if spec["symbol"]:
            result.append(spec)
    return list({
        (str(spec.get("asset_type", "")), spec["symbol"]): spec
        for spec in result
    }.values())


def resolve_bar_specs(
    ctx,
    specs: Iterable[Dict[str, Any]],
    *,
    default_asset_type: str,
    market: str = "global",
) -> List[Dict[str, Any]]:
    """Resolve configured whitelist entries and their per-security bar cursors."""
    phoenix = ctx.dept_http[DeptServices.PHOENIXA]
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for raw in specs:
        spec = dict(raw)
        spec["asset_type"] = str(
            spec.get("asset_type") or default_asset_type,
        ).strip()
        grouped[spec["asset_type"]].append(spec)

    resolved: List[Dict[str, Any]] = []
    missing: List[str] = []
    for asset_type, asset_specs in grouped.items():
        symbols = [spec["symbol"] for spec in asset_specs]
        registry = phoenix.get_securities(
            symbols=symbols,
            asset_type=asset_type,
            market=market,
            limit=max(100, len(symbols) * 2),
        )
        by_symbol = {
            row["symbol"].upper(): row
            for row in registry.values()
        }
        available = [
            (spec, by_symbol.get(spec["symbol"]))
            for spec in asset_specs
        ]
        security_ids = [
            int(row["security_id"])
            for _, row in available
            if row is not None
        ]
        last_updates = phoenix.get_bars_last_update(
            asset_type=asset_type,
            market=market,
            period="daily",
            adjust="nf",
            security_ids=security_ids,
        ) if security_ids else {}
        for spec, security in available:
            if security is None:
                missing.append(f"{asset_type}:{spec['symbol']}")
                continue
            item = {
                **spec,
                "security_id": int(security["security_id"]),
                "name": security["name"],
                "exchange": security["exchange"],
            }
            item["effective_start_date"] = incremental_start_date(
                (ctx.params or {}).get("start_date"),
                last_updates.get(item["security_id"]),
                "2015-01-01",
            )
            resolved.append(item)
    if missing:
        ctx.fail(
            "identities missing from security_registry; "
            f"run the registry task first: {missing}",
            phase="load_dynamic_parameters",
        )
        return []

    end_date = date_string(
        (ctx.params or {}).get("end_date") or pd.Timestamp.now(),
    )
    return [
        spec for spec in resolved
        if spec["effective_start_date"] <= end_date
    ]


def sink_bars_by_asset_type(
    ctx,
    rows: List[Dict[str, Any]],
    *,
    market: str = "global",
) -> None:
    by_asset_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        asset_type = row["asset_type"]
        by_asset_type[asset_type].append({
            key: value
            for key, value in row.items()
            if key != "asset_type"
        })
    phoenix = ctx.dept_http[DeptServices.PHOENIXA]
    for asset_type, bars in by_asset_type.items():
        if not phoenix.upsert_bars(
            asset_type=asset_type,
            market=market,
            period="daily",
            adjust="nf",
            bars=bars,
            run_id=ctx.run_id,
        ):
            ctx.fail(
                f"failed to sink {asset_type}/{market} bars",
                phase="sink",
            )
            return

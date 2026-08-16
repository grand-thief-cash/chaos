from __future__ import annotations

import re
from typing import Any, Dict, List

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    optional_number,
    rate_limited_call,
)
from artemis.engines.task_engine.download.zh.utils import get_security_map_for_task
from artemis.engines.task_engine.worker_unit import WorkerUnit


THS_SOURCE = "ths_consensus"
EM_SOURCE = "eastmoney_consensus"
_EM_EPS_COLUMN = re.compile(r"^(\d{4})预测每股收益$")
_THS_INST_EPS_COLUMN = re.compile(r"^预测年报每股收益(\d{4})预测$")
_THS_DETAIL_COLUMN = re.compile(r"^预测(\d{4})-平均$")
_THS_DETAIL_METRICS = {
    "每股净资产(元)": ("bvps_consensus", "cny_per_share"),
    "净资产收益率": ("roe_consensus", "ratio"),
    "每股现金流(元)": ("cfps_consensus", "cny_per_share"),
    "净利润(元)": ("net_profit_consensus", "cny"),
    "营业收入(元)": ("revenue_consensus", "cny"),
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _detail_number(value: Any, unit: str) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"--", "-"}:
        return None
    multiplier = 1.0
    if text.endswith("%"):
        text = text[:-1]
        multiplier = 0.01
    elif text.endswith("亿"):
        text = text[:-1]
        multiplier = 1e8
    elif text.endswith("万"):
        text = text[:-1]
        multiplier = 1e4
    parsed = optional_number(text)
    if parsed is None:
        return None
    return parsed * multiplier


class StockZHAEarningsConsensus(WorkerUnit):
    """Persist honest daily consensus snapshots from public providers.

    Public APIs expose *today's* consensus, not a historical point-in-time
    archive. Consequently this task never fabricates old snapshots: ``as_of``
    defaults to today and repeated runs on the same date are idempotent.
    """

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        params = ctx.params or {}
        security_map = get_security_map_for_task(ctx)
        securities = sorted(
            {int(row["security_id"]): row for row in security_map.values()}.values(),
            key=lambda row: (row["symbol"], row["security_id"]),
        )
        offset = max(int(params.get("symbol_offset", 0)), 0)
        max_symbols = min(max(int(params.get("max_symbols_per_run", 5)), 1), 50)
        securities = securities[offset:offset + max_symbols]
        if not securities:
            ctx.fail("no registered securities selected", phase="load_dynamic_parameters")
            return
        as_of = date_string(params.get("as_of_date") or pd.Timestamp.now())
        today = pd.Timestamp.now().strftime("%Y-%m-%d")
        if not as_of or as_of != today:
            ctx.fail(
                "as_of_date must equal today; public consensus APIs do not expose historical snapshots",
                phase="load_dynamic_parameters",
            )
            return
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        ths_updates = phoenix.get_market_observation_last_updates(
            source=THS_SOURCE,
            security_ids=[int(row["security_id"]) for row in securities],
        )
        force_refresh = _as_bool(params.get("force_refresh"))
        ctx.params["pending_securities"] = [
            row for row in securities
            if force_refresh or str(ths_updates.get(int(row["security_id"])) or "") < as_of
        ]
        ctx.params["as_of_date"] = as_of

    def execute(self, ctx: TaskContext):
        securities = (ctx.params or {}).get("pending_securities", [])
        ths: Dict[int, Any] = {}
        ths_institutions: Dict[int, Any] = {}
        ths_details: Dict[int, Any] = {}
        for security in securities:
            symbol = str(security["symbol"])
            ths[int(security["security_id"])] = rate_limited_call(
                ctx,
                f"stock_profit_forecast_ths:{symbol}",
                lambda symbol=symbol: ak.stock_profit_forecast_ths(
                    symbol=symbol,
                    indicator="预测年报每股收益",
                ),
            )
            ths_institutions[int(security["security_id"])] = rate_limited_call(
                ctx,
                f"stock_profit_forecast_ths:institution:{symbol}",
                lambda symbol=symbol: ak.stock_profit_forecast_ths(
                    symbol=symbol,
                    indicator="业绩预测详表-机构",
                ),
            )
            ths_details[int(security["security_id"])] = rate_limited_call(
                ctx,
                f"stock_profit_forecast_ths:detail:{symbol}",
                lambda symbol=symbol: ak.stock_profit_forecast_ths(
                    symbol=symbol,
                    indicator="业绩预测详表-详细指标预测",
                ),
            )
        em = None
        if securities and _as_bool((ctx.params or {}).get("include_eastmoney")):
            # EastMoney's AKShare API is market-wide. Call it once per task and
            # filter locally; never call the same paginated endpoint per symbol.
            em = rate_limited_call(
                ctx,
                "stock_profit_forecast_em:market",
                lambda: ak.stock_profit_forecast_em(),
            )
        return {
            "ths": ths,
            "ths_institutions": ths_institutions,
            "ths_details": ths_details,
            "em": em,
        }

    @staticmethod
    def _observation(
        *,
        source: str,
        security: Dict[str, Any],
        as_of: str,
        fiscal_year: str,
        mean: float,
        extra: Dict[str, Any],
        observation_prefix: str = "eps_consensus",
        unit: str = "cny_per_share",
    ) -> Dict[str, Any]:
        return {
            "source": source,
            "security_id": int(security["security_id"]),
            "trade_date": as_of,
            "observation_type": f"{observation_prefix}_{fiscal_year}",
            "value": mean,
            "unit": unit,
            "extra_json": {
                "symbol": security["symbol"],
                "fiscal_year": int(fiscal_year),
                "snapshot_semantics": "observed_on_fetch_date",
                **extra,
            },
        }

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        securities = {
            int(row["security_id"]): row
            for row in (ctx.params or {}).get("pending_securities", [])
        }
        as_of = str((ctx.params or {}).get("as_of_date") or "")
        keyed_rows: Dict[tuple[str, int, str], Dict[str, Any]] = {}

        def keep(row: Dict[str, Any]) -> None:
            keyed_rows[(
                str(row["source"]), int(row["security_id"]),
                str(row["observation_type"]),
            )] = row

        ths_frames = result.get("ths") or {}
        for security_id, frame in ths_frames.items():
            security = securities.get(int(security_id))
            if not security or not isinstance(frame, pd.DataFrame):
                continue
            for record in frame.to_dict("records"):
                fiscal_year = str(record.get("年度") or "").strip()
                mean = optional_number(record.get("均值"))
                if not fiscal_year.isdigit() or mean is None or mean <= 0:
                    continue
                keep(self._observation(
                    source=THS_SOURCE,
                    security=security,
                    as_of=as_of,
                    fiscal_year=fiscal_year,
                    mean=mean,
                    extra={
                        "low": optional_number(record.get("最小值")),
                        "high": optional_number(record.get("最大值")),
                        "institution_count": optional_number(record.get("预测机构数")),
                        "industry_mean": optional_number(record.get("行业平均数")),
                        "range_source": "provider_summary",
                    },
                ))

        # Prefer the active institution-detail distribution over the summary
        # endpoint's all-history min/max, which can contain stale outliers.
        institution_frames = result.get("ths_institutions") or {}
        for security_id, frame in institution_frames.items():
            security = securities.get(int(security_id))
            if not security or not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            for column in frame.columns:
                match = _THS_INST_EPS_COLUMN.match(str(column))
                if not match:
                    continue
                series = pd.to_numeric(frame[column], errors="coerce").dropna()
                series = series[series > 0]
                if series.empty:
                    continue
                report_dates = [
                    str(value)[:10] for value in frame.get("报告日期", pd.Series(dtype=str)).dropna()
                    if str(value).strip()
                ]
                keep(self._observation(
                    source=THS_SOURCE,
                    security=security,
                    as_of=as_of,
                    fiscal_year=match.group(1),
                    mean=float(series.mean()),
                    extra={
                        "low": float(series.min()),
                        "high": float(series.max()),
                        "q25": float(series.quantile(0.25)),
                        "median": float(series.median()),
                        "q75": float(series.quantile(0.75)),
                        "institution_count": int(series.count()),
                        "latest_report_date": max(report_dates) if report_dates else None,
                        "range_source": "institution_detail",
                    },
                ))

        detail_frames = result.get("ths_details") or {}
        for security_id, frame in detail_frames.items():
            security = securities.get(int(security_id))
            if not security or not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            for record in frame.to_dict("records"):
                metric = str(record.get("预测指标") or "").strip()
                metric_config = _THS_DETAIL_METRICS.get(metric)
                if not metric_config:
                    continue
                observation_prefix, unit = metric_config
                for column, raw_value in record.items():
                    match = _THS_DETAIL_COLUMN.match(str(column))
                    if not match:
                        continue
                    parsed = _detail_number(raw_value, unit)
                    if parsed is None or parsed <= 0:
                        continue
                    keep(self._observation(
                        source=THS_SOURCE,
                        security=security,
                        as_of=as_of,
                        fiscal_year=match.group(1),
                        mean=parsed,
                        extra={"metric": metric, "range_source": "detailed_indicator_mean"},
                        observation_prefix=observation_prefix,
                        unit=unit,
                    ))

        em_frame = result.get("em")
        if isinstance(em_frame, pd.DataFrame) and not em_frame.empty:
            by_symbol = {str(row["symbol"]): row for row in securities.values()}
            for record in em_frame.to_dict("records"):
                security = by_symbol.get(str(record.get("代码") or "").zfill(6))
                if not security:
                    continue
                ratings = {
                    key: optional_number(record.get(f"机构投资评级(近六个月)-{label}"))
                    for key, label in (
                        ("buy", "买入"), ("outperform", "增持"),
                        ("neutral", "中性"), ("underperform", "减持"),
                        ("sell", "卖出"),
                    )
                }
                for column, value in record.items():
                    match = _EM_EPS_COLUMN.match(str(column))
                    mean = optional_number(value)
                    if not match or mean is None or mean <= 0:
                        continue
                    keep(self._observation(
                        source=EM_SOURCE,
                        security=security,
                        as_of=as_of,
                        fiscal_year=match.group(1),
                        mean=mean,
                        extra={
                            "report_count": optional_number(record.get("研报数")),
                            "rating_counts": ratings,
                        },
                    ))
        rows = list(keyed_rows.values())
        rows.sort(key=lambda row: (
            row["source"], row["security_id"], row["observation_type"],
        ))
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        phoenix = ctx.dept_http[DeptServices.PHOENIXA]
        for source in (THS_SOURCE, EM_SOURCE):
            payload = [
                {key: value for key, value in row.items() if key != "source"}
                for row in rows if row["source"] == source
            ]
            if payload and not phoenix.upsert_market_observations(
                source=source,
                rows=payload,
                run_id=ctx.run_id,
            ):
                ctx.fail(f"failed to sink {source}", phase="sink")
                return

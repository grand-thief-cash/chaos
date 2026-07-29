from __future__ import annotations

from typing import Any, Dict, List, cast

import akshare as ak
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.download.risk_download_utils import (
    date_string,
    incremental_start_date,
    optional_number,
    rate_limited_call,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit


SUPPORTED_SYMBOLS = {
    "北向资金", "沪股通", "深股通", "南向资金", "港股通沪", "港股通深",
}

NUMERIC_FIELDS = {
    "当日成交净买额": "net_buy",
    "买入成交额": "buy_amount",
    "卖出成交额": "sell_amount",
    "历史累计净买额": "cumulative_net_buy",
    "当日资金流入": "capital_inflow",
    "当日余额": "quota_balance",
    "持股市值": "holding_market_value",
    "领涨股-涨跌幅": "leading_stock_pct_chg",
}


def _symbols(value: Any) -> List[str]:
    if isinstance(value, str):
        result = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        result = [str(item).strip() for item in value if str(item).strip()]
    else:
        result = []
    return list(dict.fromkeys(result or ["北向资金"]))


def _optional_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


class StockZhAHsgtHist(WorkerUnit):
    """AKShare stock_hsgt_hist_em for a configured symbol list."""

    def load_dynamic_parameters(self, ctx: TaskContext) -> None:
        symbols = _symbols(ctx.params.get("symbols"))
        unsupported = [symbol for symbol in symbols if symbol not in SUPPORTED_SYMBOLS]
        if unsupported:
            ctx.fail(f"unsupported HSGT symbols: {unsupported}", phase="load_dynamic_parameters")
            return
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        last_updates = phoenix.get_hsgt_last_updates(symbols)
        ctx.params["symbols"] = symbols
        ctx.params["effective_start_dates"] = {
            symbol: incremental_start_date(
                ctx.params.get("start_date"),
                last_updates.get(symbol),
                "2015-01-01",
            )
            for symbol in symbols
        }

    def execute(self, ctx: TaskContext):
        end_date = date_string(ctx.params.get("end_date") or pd.Timestamp.now())
        result = {}
        for symbol in ctx.params["symbols"]:
            if ctx.params["effective_start_dates"][symbol] > end_date:
                continue
            result[symbol] = rate_limited_call(
                ctx,
                f"stock_hsgt_hist_em:{symbol}",
                lambda symbol=symbol: ak.stock_hsgt_hist_em(symbol=symbol),
            )
        return result

    def post_process(self, ctx: TaskContext, result: Any) -> List[Dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        end_date = date_string(ctx.params.get("end_date") or pd.Timestamp.now())
        rows: List[Dict[str, Any]] = []
        for symbol, frame in result.items():
            if not isinstance(frame, pd.DataFrame):
                continue
            start_date = ctx.params["effective_start_dates"][symbol]
            for record in frame.to_dict("records"):
                trade_date = date_string(record.get("日期"))
                if not trade_date or trade_date < start_date or trade_date > end_date:
                    continue
                row: Dict[str, Any] = {
                    "symbol": symbol,
                    "trade_date": trade_date,
                }
                for source_field, target_field in NUMERIC_FIELDS.items():
                    value = optional_number(record.get(source_field))
                    if value is not None:
                        row[target_field] = value
                benchmark = (
                    record.get("沪深300")
                    if "沪深300" in record
                    else record.get("恒生指数")
                )
                benchmark_pct_chg = (
                    record.get("沪深300-涨跌幅")
                    if "沪深300-涨跌幅" in record
                    else record.get("恒生指数-涨跌幅")
                )
                if (value := optional_number(benchmark)) is not None:
                    row["benchmark_value"] = value
                if (value := optional_number(benchmark_pct_chg)) is not None:
                    row["benchmark_pct_chg"] = value
                if (value := _optional_text(record.get("领涨股"))) is not None:
                    row["leading_stock_name"] = value
                if (value := _optional_text(record.get("领涨股-代码"))) is not None:
                    row["leading_stock_symbol"] = value
                rows.append(row)
        rows.sort(key=lambda row: (row["symbol"], row["trade_date"]))
        ctx.logger.info({
            "event": "stock_zh_a_hsgt_hist_post_process",
            "row_count": len(rows),
            "symbols": ctx.params["symbols"],
            "run_id": ctx.run_id,
        })
        return rows

    def sink(self, ctx: TaskContext, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        phoenix = cast(PhoenixAClient, ctx.dept_http[DeptServices.PHOENIXA])
        if not phoenix.upsert_hsgt_daily(rows=rows, run_id=ctx.run_id):
            ctx.fail("failed to sink HSGT daily data", phase="sink")

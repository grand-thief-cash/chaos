"""OrchestratorUnit: 季频偿债能力数据下载 (baostock query_balance_data)。

Parent 任务：
  1. 从 PhoenixA 获取 symbol 列表
  2. 根据 start_date/end_date 展开为 (year, quarter) 序列
  3. 为每个 symbol × (year, quarter) 生成一个 child 任务

支持参数（ctx.params）：
  - start_date: str  — YYYY-MM-DD，起始日期
  - end_date: str    — YYYY-MM-DD，截止日期（可选，默认当前日期）
  - symbol_list: str — 逗号分隔的 symbol 列表（可选）
  - exchange: str    — 交易所过滤，如 "SH,SZ"（可选）
"""
from datetime import datetime
from typing import List, Dict, Any, cast

import baostock as bs

from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit
from artemis.engines.task_engine.download.zh.utils import (
    date_range_to_year_quarters,
    symbol_exchange_to_bs_code,
)


class StockZhABsBalanceParent(OrchestratorUnit):

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params
        start_date = params.get("start_date")
        if not start_date:
            ctx.fail("Missing required param: start_date", phase='parameter_check')

    def load_dynamic_parameters(self, ctx: TaskContext):
        params = ctx.params

        # Parse symbol_list (optional)
        symbol_list_str = str(params.get("symbol_list", "") or "").strip()
        symbols = []
        if symbol_list_str:
            symbols = [s.strip() for s in symbol_list_str.split(",") if s.strip()]

        # Parse exchange filter
        exchange_str = str(params.get("exchange", "") or "").strip()
        exchanges = [e.strip().upper() for e in exchange_str.split(",") if e.strip()] or None

        # Get securities from PhoenixA
        phoenix_client = ctx.dept_http[DeptServices.PHOENIXA]
        client = cast(PhoenixAClient, phoenix_client)
        symbol_infos = client.get_securities(symbols=symbols or None, exchanges=exchanges)
        ctx.params["symbol_infos"] = symbol_infos

    def before_execute(self, ctx: TaskContext) -> None:
        params = ctx.params
        start_date = params.get("start_date")
        if not start_date:
            ctx.fail("Missing start_date after merge", phase='before_execute')
            return

        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            ctx.fail(f"Invalid start_date format: {start_date}", phase='before_execute')
            return

        lg = bs.login()
        if getattr(lg, 'error_code', None) != '0':
            ctx.fail(f"baostock login failed: {getattr(lg, 'error_msg', 'unknown')}", phase='before_execute')

    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        params = ctx.params
        start_date = params.get("start_date")
        end_date = params.get("end_date") or datetime.now().strftime("%Y-%m-%d")
        symbol_infos = params.get("symbol_infos", {})

        year_quarters = date_range_to_year_quarters(start_date, end_date)
        if not year_quarters:
            ctx.fail(f"No valid year/quarters from {start_date} to {end_date}", phase='plan')
            return []

        child_specs = []
        for _, info in symbol_infos.items():
            symbol = info.get("symbol")
            exchange = info.get("exchange")
            if not symbol or not exchange:
                continue

            bs_code = symbol_exchange_to_bs_code(symbol, exchange)
            if not bs_code:
                continue

            for year, quarter in year_quarters:
                child_specs.append({
                    "key": TaskCode.STOCK_ZH_A_BS_BALANCE_CHILD,
                    "params": {
                        "bs_code": bs_code,
                        "symbol": symbol,
                        "year": year,
                        "quarter": quarter,
                    },
                })

        ctx.logger.info({
            "event": "bs_balance_parent_plan_complete",
            "run_id": ctx.run_id,
            "total_symbols": len(symbol_infos),
            "total_year_quarters": len(year_quarters),
            "generated_tasks": len(child_specs),
        })
        return child_specs

    def finalize(self, ctx: TaskContext):
        bs.logout()


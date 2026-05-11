"""OrchestratorUnit: 除权除息数据下载 (baostock query_dividend_data)。

Parent 任务：
  1. 从 PhoenixA 获取 symbol 列表
  2. 根据 start_date/end_date 展开为 year 列表
  3. 为每个 symbol × year 生成一个 child 任务

支持参数（ctx.params）：
  - start_date: str  — YYYY-MM-DD，起始年份
  - end_date: str    — YYYY-MM-DD，截止年份（可选，默认当前年）
  - year_type: str   — "report"（预案公告年份）或 "operate"（除权除息年份），默认 "report"
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
from artemis.engines.task_engine.download.zh.utils import symbol_exchange_to_bs_code


class StockZhABsDividendParent(OrchestratorUnit):

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params
        start_date = params.get("start_date")
        if not start_date:
            ctx.fail("Missing required param: start_date", phase='parameter_check')

    def load_dynamic_parameters(self, ctx: TaskContext):
        params = ctx.params

        symbol_list_str = str(params.get("symbol_list", "") or "").strip()
        symbols = []
        if symbol_list_str:
            symbols = [s.strip() for s in symbol_list_str.split(",") if s.strip()]

        exchange_str = str(params.get("exchange", "") or "").strip()
        exchanges = [e.strip().upper() for e in exchange_str.split(",") if e.strip()] or None

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
        year_type = params.get("year_type", "report")
        symbol_infos = params.get("symbol_infos", {})

        try:
            start_year = datetime.strptime(start_date, "%Y-%m-%d").year
            end_year = datetime.strptime(end_date, "%Y-%m-%d").year
        except (ValueError, TypeError):
            ctx.fail(f"Cannot parse year from dates: {start_date} / {end_date}", phase='plan')
            return []

        years = list(range(start_year, end_year + 1))
        if not years:
            ctx.fail(f"No valid years from {start_date} to {end_date}", phase='plan')
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

            for year in years:
                child_specs.append({
                    "key": TaskCode.STOCK_ZH_A_BS_DIVIDEND_CHILD,
                    "params": {
                        "bs_code": bs_code,
                        "symbol": symbol,
                        "year": str(year),
                        "year_type": year_type,
                    },
                })

        ctx.logger.info({
            "event": "bs_dividend_parent_plan_complete",
            "run_id": ctx.run_id,
            "total_symbols": len(symbol_infos),
            "total_years": len(years),
            "generated_tasks": len(child_specs),
        })
        return child_specs

    def finalize(self, ctx: TaskContext):
        bs.logout()


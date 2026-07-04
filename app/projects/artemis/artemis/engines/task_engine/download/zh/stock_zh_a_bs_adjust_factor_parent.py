"""OrchestratorUnit: 复权因子下载 (baostock query_adjust_factor)。

Parent 任务：
  1. 从 PhoenixA 获取 symbol 列表
  2. 为每个 symbol 生成一个 child 任务
  3. child 按 start_date/end_date 查询该 symbol 的完整复权因子区间

支持参数（ctx.params）：
  - start_date: str  — YYYY-MM-DD，起始日期（可选）
  - end_date: str    — YYYY-MM-DD，截止日期（可选，默认当天）
  - symbol_list: str — 逗号分隔的 symbol 列表（可选）
  - exchange: str    — 交易所过滤，如 "SH,SZ"（可选）
"""
from datetime import datetime
from typing import Any, Dict, List, cast

import baostock as bs

from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.download.zh.utils import symbol_exchange_to_bs_code
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit


class StockZhABsAdjustFactorParent(OrchestratorUnit):

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
        for field in ["start_date", "end_date"]:
            val = params.get(field)
            if not val:
                continue
            try:
                datetime.strptime(val, "%Y-%m-%d")
            except (ValueError, TypeError):
                ctx.fail(f"Invalid {field} format: {val}, expected YYYY-MM-DD", phase='before_execute')
                return

        lg = bs.login()
        if getattr(lg, 'error_code', None) != '0':
            ctx.fail(f"baostock login failed: {getattr(lg, 'error_msg', 'unknown')}", phase='before_execute')

    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        params = ctx.params
        start_date = params.get("start_date")
        end_date = params.get("end_date") or datetime.now().strftime("%Y-%m-%d")
        symbol_infos = params.get("symbol_infos", {})

        child_specs = []
        for _, info in symbol_infos.items():
            symbol = info.get("symbol")
            exchange = info.get("exchange")
            security_id = info.get("security_id")
            if not symbol or not exchange or not security_id:
                # No security_id → cannot write (Phase 3 orphan defense); skip.
                continue

            bs_code = symbol_exchange_to_bs_code(symbol, exchange)
            if not bs_code:
                continue

            child_specs.append({
                "key": TaskCode.STOCK_ZH_A_BS_ADJUST_FACTOR_CHILD,
                "params": {
                    "bs_code": bs_code,
                    "symbol": symbol,
                    "security_id": int(security_id),
                    "start_date": start_date,
                    "end_date": end_date,
                },
            })

        ctx.logger.info({
            "event": "bs_adjust_factor_parent_plan_complete",
            "run_id": ctx.run_id,
            "total_symbols": len(symbol_infos),
            "generated_tasks": len(child_specs),
            "start_date": start_date,
            "end_date": end_date,
        })
        return child_specs

    def finalize(self, ctx: TaskContext):
        bs.logout()


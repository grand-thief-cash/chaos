from datetime import datetime, timedelta
from typing import List, Dict, Any, cast

import baostock as bs
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit

from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.download.zh.utils import convert_to_baostock_params


class StockZhAHistParent(OrchestratorUnit):

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params
        period = params.get("period")
        adjust = params.get("adjust")
        if not period or not adjust:
            ctx.fail(f"Missing required input params: period={period}, adjust={adjust}", phase='parameter_check')
            return


    def load_dynamic_parameters(self, ctx: TaskContext):
        params = ctx.params

        symbol_list_str = str(params.get("symbol_list", "") or "").strip()
        symbols = []
        if symbol_list_str != "":
            symbols = [s.strip() for s in symbol_list_str.split(",") if s.strip()]
            if not symbols:
                ctx.fail(f"Failed to parse symbol_list: {symbol_list_str}", phase='load_dynamic_parameters')
                return

        # Parse exchange filter from config
        exchange_str = str(params.get("exchange", "") or "").strip()
        exchanges = [e.strip().upper() for e in exchange_str.split(",") if e.strip()] or None

        # Get securities from PhoenixA, filtered by exchanges
        phoenix_client = ctx.dept_http[DeptServices.PHOENIXA]
        client = cast(PhoenixAClient, phoenix_client)
        symbol_infos = client.get_securities(symbols=symbols or None, exchanges=exchanges)

        symbols = list(symbol_infos.keys())
        period = params.get("period")
        adjust = params.get("adjust")

        # Phase 4: query last_update by security_id (the registry already gave us
        # security_id on each info row; passing security_ids avoids a redundant
        # symbol→id resolve inside the client). The response stays {symbol: date}.
        security_ids = [int(i.get("security_id")) for i in symbol_infos.values() if i.get("security_id")]
        last_updates_map = client.get_bars_last_update(
            period=period, adjust=adjust, security_ids=security_ids or None,
        )

        ctx.params["last_updates_map"] = last_updates_map
        ctx.params["symbol_infos"] = symbol_infos



    def before_execute(self, ctx: TaskContext) -> None:
        """
        Optional hook before planning child tasks.
        Can be used to validate parameters or set up shared resources.
        """
        ctx.logger.info({
            "event": "stock_zh_a_hist_parent_before_plan",
            "run_id": ctx.run_id,
            "msg": "Starting to plan child tasks for stock_zh_a_hist"
        })

        # extract params
        params = ctx.params or {}

        start_date = params.get("start_date")
        fields = params.get("fields")

        # params check
        if not start_date or not fields:
            ctx.fail(f"Missing execution params: start_date={start_date}, fields={fields}", phase='before_execute')
            return

        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            ctx.fail(f"Invalid start_date format: {start_date}, expected YYYY-MM-DD", phase='before_execute')
            return

        lg = bs.login()
        if getattr(lg, 'error_code', None) != '0':
            ctx.fail(f"baostock login failed: {getattr(lg, 'error_msg', 'unknown error')}", phase='before_execute')
            return


    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """
        Load parameters for child tasks.
        Each child task needs: bs_code, symbol, start_date, end_date (opt), period, adjust
        """
        # ctx.params holds the merged configuration for this task execution
        params = ctx.params

        # 1. Extract all parameters from config
        period = params.get("period")
        adjust = params.get("adjust")
        start_date = params.get("start_date")
        fields = params.get("fields")
        symbol_infos = params.get("symbol_infos", {})
        last_updates_map = params.get("last_updates_map", {})


        # 2. Get last update dates for stocks (prefer filtered)
        bs_frequency = convert_to_baostock_params("frequency", period)
        bs_adjust = convert_to_baostock_params("adjustflag", adjust)
        if not bs_frequency or not bs_adjust:
            ctx.fail(f"Invalid baostock schema mapping: period={period}, adjust={adjust}", phase='plan')
            return []


        child_specs = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        base_start_date = start_date

        for _, info in symbol_infos.items():
            symbol = info.get("symbol")
            exchange = info.get("exchange")
            security_id = info.get("security_id")
            item_start_date = base_start_date

            if not symbol or not exchange or not security_id:
                ctx.fail(f"Missing stock info from PhoenixA: symbol={symbol}, exchange={exchange}, security_id={security_id}", phase='plan')
                return []

            if exchange in ["SH", "SZ","BJ"]:
                bs_code = f"{exchange.lower()}.{symbol}"
            else:
                ctx.fail(f"Cannot determine bs_code for symbol={symbol}, exchange={exchange}", phase='plan')
                return []

            # last_updates_map key is the symbol (e.g. "600000")
            last_update = last_updates_map.get(symbol)

            if last_update:
                try:
                    # Assuming last_update is YYYY-MM-DD
                    last_date_obj = datetime.strptime(last_update, "%Y-%m-%d")
                except ValueError:
                    ctx.fail(f"Invalid last_update format from PhoenixA for symbol={symbol}: {last_update}", phase='plan')
                    return []

                start_date_obj = last_date_obj + timedelta(days=1)
                if start_date_obj > datetime.now():
                    continue  # Already up to date
                item_start_date = start_date_obj.strftime("%Y-%m-%d")

            if item_start_date > today_str:
                continue

            child_params = {
                "bs_code": bs_code,
                "symbol": symbol,
                "security_id": int(security_id),
                "start_date": item_start_date,
                "end_date": today_str,
                "adjust": adjust,
                "period": period,
                "bs_adjust": bs_adjust,
                "bs_period": bs_frequency,
                "fields": fields
            }

            child_specs.append({
                "key": TaskCode.STOCK_ZH_A_HIST_CHILD,
                "params": child_params
            })


        ctx.logger.info({
            "event": "stock_zh_a_hist_parent_plan_complete",
            "run_id": ctx.run_id,
            "total_symbols": len(symbol_infos),
            "generated_tasks": len(child_specs),
        })

        return child_specs

    def finalize(self, ctx: TaskContext):
        bs.logout()
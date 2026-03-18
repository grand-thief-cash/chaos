from datetime import datetime, timedelta
from typing import List, Dict, Any, cast

import baostock as bs

from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.task_units.download.zh.utils import convert_baostock_to_phoenix_schema
from artemis.task_units.parent import OrchestratorTaskUnit


class StockZhAHistParent(OrchestratorTaskUnit):

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params
        period = params.get("period")
        adjust = params.get("adjust")
        if not period or not adjust:
            raise RuntimeError(f"Missing required input params: period={period}, adjust={adjust}")


    def load_dynamic_parameters(self, ctx: TaskContext):
        params = ctx.incoming_params

        code_list_str = params.get("code_list", "")
        codes = []
        if code_list_str != "":
            codes = code_list_str.split(",")
            if codes is None:
                raise RuntimeError(f"Failed to parse code_list: {code_list_str}")

        # Get stock codes and exchanges from PhoenixA, optionally filtered by target_codes
        phoenix_client = ctx.dept_http[DeptServices.PHOENIXA]
        client = cast(PhoenixAClient, phoenix_client)
        code_infos = client.get_stock_zh_a_codes(codes=codes or None)
        codes = list(code_infos.keys())
        period = params.get("period")
        adjust = params.get("adjust")

        last_updates_map = client.get_stock_zh_a_last_updates(period, adjust, codes=codes or None)

        ctx.params["last_updates_map"] = last_updates_map
        ctx.params["code_infos"] = code_infos



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
            raise RuntimeError(f"Missing execution params: start_date={start_date}, fields={fields}")

        lg = bs.login()


    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """
        Load parameters for child tasks.
        Each child task needs: code, start_date, end_date (opt), frequency, adjust
        """
        # ctx.params holds the merged configuration for this task execution
        params = ctx.params
        # task_conf = params.get("config", config)

        # 1. Pop-up all parameter from config
        period = params.get("period")
        adjust = params.get("adjust")
        start_date = params.get("start_date")
        fields = params.get("fields")
        code_infos = params.get("code_infos", {})
        last_updates_map = params.get("last_updates_map", {})


        # 2. Get last update dates for stocks (prefer filtered)
        frequency = convert_baostock_to_phoenix_schema("frequency", period)
        adjust = convert_baostock_to_phoenix_schema("adjustflag", adjust)


        child_specs = []
        today_str = datetime.now().strftime("%Y-%m-%d")

        for _, info in code_infos.items():
            code = info.get("code")
            exchange = info.get("exchange")

            if exchange in ["SH", "SZ","BJ"]:
                bs_code = f"{exchange.lower()}.{code}"
            else:
                ctx.logger.error({
                    "event": "stock_zh_a_hist_parent_invalid_code",
                    "run_id": ctx.run_id,
                    "code": code,
                    "exchange": exchange,
                    "msg": "Cannot determine bs_code for stock"
                })
                return []

            try:
                # last_updates_map key is likely the raw code (6 digits)
                last_update = last_updates_map.get(code)

                if last_update:
                    try:
                        # Assuming last_update is YYYY-MM-DD
                        last_date_obj = datetime.strptime(last_update, "%Y-%m-%d")
                        start_date_obj = last_date_obj + timedelta(days=1)
                        if start_date_obj > datetime.now():
                            continue # Already up to date
                        start_date = start_date_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        ctx.logger.warning({
                            "event": "stock_zh_a_hist_parent_date_parse_error",
                            "run_id": ctx.run_id,
                            "code": code,
                            "last_update": last_update,
                            "msg": "Invalid date format from PhoenixA"
                        })
                        pass

                if start_date > today_str:
                    continue

                child_params = {
                    "code": bs_code,
                    "raw_code": code,
                    "start_date": start_date,
                    "end_date": today_str,
                    "frequency": frequency,
                    "adjustflag": adjust,
                    "fields": fields
                }

                child_specs.append({
                    "key": TaskCode.STOCK_ZH_A_HIST_CHILD, # FIX: Use actual registered task code
                    "params": child_params
                })

            except Exception as e:
                ctx.logger.error({
                    "event": "stock_zh_a_hist_parent_item_error",
                    "run_id": ctx.run_id,
                    "code": code,
                    "error": str(e)
                })
                continue

        ctx.logger.info({
            "event": "stock_zh_a_hist_parent_plan_complete",
            "run_id": ctx.run_id,
            "total_codes": len(code_infos),
            "generated_tasks": len(child_specs),
        })

        return child_specs

    def finalize(self, ctx: TaskContext):
        bs.logout()
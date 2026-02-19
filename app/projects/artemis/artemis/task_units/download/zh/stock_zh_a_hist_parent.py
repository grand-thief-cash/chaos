from datetime import datetime, timedelta
from typing import List, Dict, Any, cast

from artemis.consts import DeptServices, TaskCode, SDK_NAME
from artemis.core import TaskContext, sdk_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.task_units.parent import OrchestratorTaskUnit
from artemis.utils import parse_list_param


class StockZhAHistParent(OrchestratorTaskUnit):
    """
    Parent task unit for downloading stock data.
    """

    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """
        Load parameters for child tasks.
        Each child task needs: code, start_date, end_date (opt), frequency, adjust
        """
        # ctx.params holds the merged configuration for this task execution
        config = ctx.params or {}
        task_conf = config.get("config", config)

        frequency = task_conf.get("frequency")
        adjust = task_conf.get("adjustflag")
        default_start_date = task_conf.get("start_date")
        fields = task_conf.get("fields")

        # Optional: run only specified codes
        code_list_raw = task_conf.get("code_list")
        target_codes = parse_list_param(code_list_raw)
        if code_list_raw and not target_codes:
            ctx.logger.warning({
                "event": "stock_zh_a_hist_parent_empty_code_list",
                "run_id": ctx.run_id,
                "code_list": code_list_raw,
                "msg": "code_list provided but parsed empty"
            })
            return []

        if not frequency or not adjust or not default_start_date or not fields:
            ctx.logger.error({
                "event": "stock_zh_a_hist_parent_missing_params",
                "run_id": ctx.run_id,
                "msg": f"Missing required params: frequency={frequency}, adjustflag={adjust}, start_date={default_start_date}, fields={fields}"
            })
            return []

        phoenix_client = ctx.dept_http[DeptServices.PHOENIXA]
        client = cast(PhoenixAClient, phoenix_client)

        # 1. Get stock codes from PhoenixA (full or filtered)
        if not hasattr(client, 'get_all_stock_codes'):
            ctx.logger.error({
                "event": "stock_zh_a_hist_parent_client_type_mismatch",
                "run_id": ctx.run_id,
                "client_type": str(type(client))
            })
            return []

        stock_infos = client.get_all_stock_codes(codes=target_codes or None)
        if not stock_infos:
            ctx.logger.warning({
                "event": "stock_zh_a_hist_parent_no_codes",
                "run_id": ctx.run_id,
                "msg": "No stock codes found from PhoenixA"
            })
            return []

        # 2. Get last update dates for stocks (prefer filtered)
        last_updates_map = client.get_stock_last_updates(frequency, adjust, codes=target_codes or None)

        child_specs = []
        today_str = datetime.now().strftime("%Y-%m-%d")

        for info in stock_infos:
            raw_code = info.get("code")
            exchange = info.get("exchange")

            if not raw_code:
                continue

            if exchange and exchange.upper() in ["SH", "SZ","BJ"]:
                bs_code = f"{exchange.lower()}.{raw_code}"
            else:
                ctx.logger.error({
                    "event": "stock_zh_a_hist_parent_invalid_code",
                    "run_id": ctx.run_id,
                    "code": raw_code,
                    "exchange": exchange,
                    "msg": "Cannot determine bs_code for stock"
                })
                return []

            try:
                start_date = default_start_date
                # last_updates_map key is likely the raw code (6 digits)
                last_update = last_updates_map.get(raw_code)

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
                            "code": raw_code,
                            "last_update": last_update,
                            "msg": "Invalid date format from PhoenixA"
                        })
                        pass

                if start_date > today_str:
                    continue

                child_params = {
                    "code": bs_code,
                    "row_code": raw_code,
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
                    "code": raw_code,
                    "error": str(e)
                })
                continue

        ctx.logger.info({
            "event": "stock_zh_a_hist_parent_plan_complete",
            "run_id": ctx.run_id,
            "total_codes": len(stock_infos),
            "generated_tasks": len(child_specs),
            "code_filter_size": len(target_codes)
        })

        return child_specs

    def before_execute(self, ctx: TaskContext) -> None:
        """
        Optional hook before executing child tasks.
        """
        sdk_mgr.get_sdk(SDK_NAME.BAOSTOCK)
        ctx.logger.info({
            "event": "stock_zh_a_hist_parent_before_execute",
            "run_id": ctx.run_id,
            "msg": "Activating baostock login session for child tasks"
        })
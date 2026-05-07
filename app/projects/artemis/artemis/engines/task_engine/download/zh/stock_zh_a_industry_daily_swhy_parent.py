from typing import Any, Dict, List

from artemis import consts
from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit
from artemis.engines.task_engine.download.zh.stock_zh_a_industry_weight_swhy_parent import _resolve_index_codes


class StockZHAIndustryDailySWHY(OrchestratorUnit):
    """申万行业日线编排任务：按行业指数拆分为子任务，每个指数一个 CHILD。"""

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params or {}
        symbols = params.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            ctx.fail(f"symbols must be a list of index codes (e.g. ['851426.SI']), got {type(symbols).__name__}", phase='parameter_check')
            return

    def before_execute(self, ctx: TaskContext) -> None:
        from artemis.core.sdk.manager import sdk_mgr
        from artemis.consts import SDK_NAME

        try:
            sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
        except Exception as e:
            ctx.fail(f"failed to acquire AmazingData SDK: {e}", phase='before_execute')
            return

    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        code_list = _resolve_index_codes(ctx)

        if not code_list:
            ctx.fail("no valid industry index codes resolved", phase='plan')
            return []

        params = ctx.params or {}
        child_specs = []
        for code in code_list:
            child_specs.append({
                "key": TaskCode.STOCK_ZH_A_INDUSTRY_DAILY_SWHY_CHILD,
                "params": {
                    "index_code": code,
                    "start_date": params.get("start_date"),
                    "end_date": params.get("end_date"),
                },
            })

        ctx.logger.info({
            'event': 'swhy_daily_plan_complete',
            'total_codes': len(code_list),
            'run_id': ctx.run_id,
        })
        return child_specs

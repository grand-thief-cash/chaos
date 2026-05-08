from typing import Any, Dict, List, Optional

from artemis import consts
from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit


def _resolve_index_codes(ctx: TaskContext) -> Optional[List[str]]:
    """Resolve industry index code list from params or PhoenixA.

    For industry tasks, `index_codes` is a list of index codes already in SDK format
    (e.g. ["851426.SI"]). Unlike stock tasks, no `exchange` parameter is needed.

    Returns: list of index codes, or None on failure.
    """
    params = ctx.params or {}
    raw = params.get("index_codes")
    if raw:
        if isinstance(raw, str):
            raw = [s.strip() for s in raw.split(",") if s.strip()]
        if isinstance(raw, list) and raw:
            return [str(s).strip() for s in raw if str(s).strip()]

    # No explicit index_codes → query PhoenixA for all SWHY industry index codes
    phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
    categories = phoenixA_client.query_industry_categories(
        source=consts.DataSource.DS_AMAZING_DATA.value,
        taxonomy=consts.Taxonomy.SWHY.value,
        market="zh_a",
        page_size=9999,
    )
    return [item["index_code"] for item in categories.get("list", []) if item.get("index_code")]


class StockZHAIndustryWeightSWHY(OrchestratorUnit):
    """申万行业权重编排任务：按行业指数拆分为子任务，每个指数一个 CHILD。"""

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params or {}
        index_codes = params.get("index_codes")
        if index_codes is not None and not isinstance(index_codes, list):
            ctx.fail(f"index_codes must be a list of index codes (e.g. ['851426.SI']), got {type(index_codes).__name__}", phase='parameter_check')
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
                "key": TaskCode.STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY_CHILD,
                "params": {
                    "index_code": code,
                    "start_date": params.get("start_date"),
                    "end_date": params.get("end_date"),
                },
            })

        ctx.logger.info({
            'event': 'swhy_weight_plan_complete',
            'total_codes': len(code_list),
            'run_id': ctx.run_id,
        })
        return child_specs

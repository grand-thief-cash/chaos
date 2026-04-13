import os
from typing import Any, Dict, List

import AmazingData as ad

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


class StockZHAMarketCategorySWHY(WorkerUnit):
    """下载申万行业分类数据（来源：AmazingData InfoData）。"""

    def before_execute(self, ctx: TaskContext) -> None:
        from artemis.core.sdk.manager import sdk_mgr
        from artemis.consts import SDK_NAME

        try:
            # 触发 login
            sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
        except Exception as e:
            ctx.fail(f"failed to acquire AmazingData SDK: {e}", phase='before_execute')
            return

        self._info_data = ad.InfoData()

    def execute(self, ctx):
        from artemis.core.config_manager import cfg_mgr

        task_engine_cfg = cfg_mgr.task_engine_config()
        cache_dir = os.path.abspath(task_engine_cfg.amazing_data_cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        try:
            result = self._info_data.get_industry_base_info(local_path=cache_dir, is_local=False)
            return result
        except Exception as e:
            ctx.fail(f"fetch SWHY industry base info failed: {e}", phase='execute')
            return {}

    def post_process(self, ctx: TaskContext, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        import pandas as pd

        df = pd.DataFrame(result)
        if df.empty:
            return []

        processed = []
        for _, row in df.iterrows():
            processed.append({
                "index_code": str(row.get("INDEX_CODE", "")),
                "industry_code": str(row.get("INDUSTRY_CODE", "")),
                "level_type": int(row.get("LEVEL_TYPE", 0)),
                "level1_name": str(row.get("LEVEL1_NAME", "")),
                "level2_name": str(row.get("LEVEL2_NAME", "")),
                "level3_name": str(row.get("LEVEL3_NAME", "")),
                "is_pub": int(row.get("IS_PUB", 0)),
                "change_reason": str(row.get("CHANGE_REASON", "")),
            })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': 'swhy_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = phoenixA_client.upsert_market_categories(
            processed, consts.DataSource.DS_AMAZING_DATA.value, ctx.run_id
        )
        if ok is False:
            ctx.fail("failed to sink SWHY market categories to phoenixA", phase='sink')

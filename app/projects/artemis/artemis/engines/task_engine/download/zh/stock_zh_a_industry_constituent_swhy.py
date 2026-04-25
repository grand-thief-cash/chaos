import os
from typing import Any, Dict, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


class StockZHAIndustryConstituentSWHY(WorkerUnit):
    """下载申万行业指数成分股数据（来源：AmazingData InfoData get_industry_constituent）。"""

    def before_execute(self, ctx: TaskContext) -> None:
        from artemis.core.sdk.manager import sdk_mgr
        from artemis.consts import SDK_NAME

        try:
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
            # 先获取行业基本信息，取得指数代码列表
            base_info = self._info_data.get_industry_base_info(local_path=cache_dir, is_local=False)
            industry_base_list = list(base_info['INDEX_CODE'])

            # 获取行业指数成分股
            result = self._info_data.get_industry_constituent(
                industry_base_list, local_path=cache_dir, is_local=False
            )
            return result
        except Exception as e:
            ctx.fail(f"fetch SWHY industry constituent failed: {e}", phase='execute')
            return {}

    def post_process(self, ctx: TaskContext, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        processed = []
        for code, df in result.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for _, row in df.iterrows():
                processed.append({
                    "index_code": str(row.get("INDEX_CODE", code)),
                    "con_code": str(row.get("CON_CODE", "")),
                    "indate": str(row.get("INDATE", "")),
                    "outdate": str(row.get("OUTDATE", "")),
                    "index_name": str(row.get("INDEX_NAME", "")),
                })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': 'swhy_constituent_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = phoenixA_client.upsert_industry_constituents(
            processed, consts.DataSource.DS_AMAZING_DATA.value, ctx.run_id
        )
        if ok is False:
            ctx.fail("failed to sink SWHY industry constituents to phoenixA", phase='sink')


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
        import json

        import pandas as pd

        df = pd.DataFrame(result)
        if df.empty:
            return []

        # Build INDUSTRY_CODE → INDEX_CODE lookup for parent resolution
        code_map: Dict[str, str] = {}
        for _, row in df.iterrows():
            ic = str(row.get("INDUSTRY_CODE", "")).strip()
            idx = str(row.get("INDEX_CODE", "")).strip()
            if ic and idx:
                code_map[ic] = idx

        processed = []
        for _, row in df.iterrows():
            index_code = str(row.get("INDEX_CODE", "")).strip()
            industry_code = str(row.get("INDUSTRY_CODE", "")).strip()
            level_type = int(row.get("LEVEL_TYPE", 0))

            # Name based on level
            if level_type == 1:
                name = str(row.get("LEVEL1_NAME", ""))
            elif level_type == 2:
                name = str(row.get("LEVEL2_NAME", ""))
            elif level_type == 3:
                name = str(row.get("LEVEL3_NAME", ""))
            else:
                name = ""

            # Parent code: derive from INDUSTRY_CODE hierarchy
            # SWHY: level-1 = 2-char, level-2 = 4-char, level-3 = 6-char
            parent_code = None
            if level_type == 2 and len(industry_code) >= 4:
                parent_code = code_map.get(industry_code[:2])
            elif level_type == 3 and len(industry_code) >= 6:
                parent_code = code_map.get(industry_code[:4])

            # Extra attributes
            attrs = {}
            is_pub = row.get("IS_PUB")
            change_reason = row.get("CHANGE_REASON")
            if is_pub is not None and int(is_pub) != 0:
                attrs["is_pub"] = int(is_pub)
            if change_reason and str(change_reason).strip():
                attrs["change_reason"] = str(change_reason)

            entry = {
                "code": index_code,
                "name": name,
                "parent_code": parent_code,
                "level": level_type,
                "is_leaf": level_type == 3,
            }
            if attrs:
                entry["attrs"] = json.dumps(attrs, ensure_ascii=False)

            processed.append(entry)
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

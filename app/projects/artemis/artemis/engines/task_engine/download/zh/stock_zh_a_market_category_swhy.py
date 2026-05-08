import os
from typing import Any, Dict, List

import AmazingData as ad

from artemis import consts
from artemis.consts import DeptServices, Taxonomy
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


class StockZHAMarketCategorySWHY(WorkerUnit):
    """下载申万行业分类数据（来源：AmazingData InfoData）。"""

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

        # Build name-based parent lookups
        # LEVEL1_NAME identifies level-1 nodes; (LEVEL1_NAME, LEVEL2_NAME) identifies level-2 nodes
        level1_by_name: Dict[str, str] = {}         # LEVEL1_NAME → INDUSTRY_CODE
        level2_by_names: Dict[tuple, str] = {}       # (LEVEL1_NAME, LEVEL2_NAME) → INDUSTRY_CODE
        for _, row in df.iterrows():
            ic = str(row.get("INDUSTRY_CODE", "")).strip()
            level_type = int(row.get("LEVEL_TYPE", 0))
            if level_type == 1:
                level1_by_name[str(row.get("LEVEL1_NAME", "")).strip()] = ic
            elif level_type == 2:
                key = (str(row.get("LEVEL1_NAME", "")).strip(),
                       str(row.get("LEVEL2_NAME", "")).strip())
                level2_by_names[key] = ic

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

            # Parent code: use name hierarchy matching (more robust than code prefix matching)
            parent_code = None
            if level_type == 2:
                parent_name = str(row.get("LEVEL1_NAME", "")).strip()
                parent_code = level1_by_name.get(parent_name)
            elif level_type == 3:
                parent_key = (str(row.get("LEVEL1_NAME", "")).strip(),
                              str(row.get("LEVEL2_NAME", "")).strip())
                parent_code = level2_by_names.get(parent_key)

            # Extra attributes (only non-standard fields)
            attrs = {}
            is_pub = row.get("IS_PUB")
            change_reason = row.get("CHANGE_REASON")
            if is_pub is not None and int(is_pub) != 0:
                attrs["is_pub"] = int(is_pub)
            if change_reason and str(change_reason).strip() and str(change_reason).strip() != "nan":
                attrs["change_reason"] = str(change_reason).strip()

            entry = {
                "code": industry_code,
                "name": name,
                "parent_code": parent_code,
                "index_code": index_code if index_code else None,
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
            processed,
            consts.DataSource.DS_AMAZING_DATA.value,
            taxonomy=Taxonomy.SWHY.value,
            market="zh_a",
            run_id=ctx.run_id,
        )
        if ok is False:
            ctx.fail("failed to sink SWHY market categories to phoenixA", phase='sink')

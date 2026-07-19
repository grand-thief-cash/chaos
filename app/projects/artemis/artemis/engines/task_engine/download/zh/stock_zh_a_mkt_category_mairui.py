from typing import Any, Dict, List

import requests
from artemis.engines.task_engine.worker_unit import WorkerUnit

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.config_manager import cfg_mgr


class StockZHAMktCategoryMairui(WorkerUnit):

    def execute(self, ctx):
        sdk_cfg = cfg_mgr.get_config().sdk.get('mairui', {})
        license_key = sdk_cfg.get('license', '')
        if not license_key:
            ctx.fail("mairui license not configured (sdk.mairui.license)", phase='execute')
            return []
        url = f"https://api.mairuiapi.com/hszg/list/{license_key}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()  # expected to be a JSON array
            return data
        except Exception as e:
            ctx.fail(f"fetch market category failed: {e}", phase='execute')
            return []

    def post_process(self, ctx: TaskContext, result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # 把pcode 转换成parent_code, pname 转换成 parent_name，code
        processed = []
        for item in result:
            processed.append({
                "parent_code": item.get("pcode"),
                "parent_name": item.get("pname"),
                "code": item.get("code"),
                "name": item.get("name"),
                "type1": item.get("type1"),
                "type2": item.get("type2"),
                "level": item.get("level"),
                "is_leaf": True if item.get("isleaf") == 1 else False,
            })
        return processed


    def sink(self, ctx, processed: List[Dict[str, Any]]):
        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = phoenixA_client.upsert_taxonomy_categories(
            processed,
            source=consts.DataSource.DS_MAIRUI.value,
            taxonomy=consts.Taxonomy.MAIRUI.value,
            market="zh_a",
            run_id=ctx.run_id,
        )
        if ok is False:
            ctx.fail("failed to sink market categories to phoenixA", phase='sink')

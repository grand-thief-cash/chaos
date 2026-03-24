from typing import Any, Dict, List

import requests
from artemis.task_units.worker_unit import WorkerUnit

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext


class StockZHAMarketCategory(WorkerUnit):

    def execute(self, ctx):
        url = "https://api.mairuiapi.com/hszg/list/LICENCE-66D8-9F96-0C7F0FBCD073"
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
        ok = phoenixA_client.upsert_market_categories(processed, consts.DataSource.DS_MAIRUI.value, ctx.run_id)
        if ok is False:
            ctx.fail("failed to sink market categories to phoenixA", phase='sink')

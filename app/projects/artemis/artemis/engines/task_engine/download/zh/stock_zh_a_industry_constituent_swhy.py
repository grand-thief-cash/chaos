import os
from typing import Any, Dict, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices, Taxonomy
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.download.zh.stock_zh_a_industry_weight_swhy_parent import _resolve_index_codes


class StockZHAIndustryConstituentSWHY(WorkerUnit):
    """下载申万行业指数成分股数据。

    ctx.params:
      - symbols: list[str] — 行业指数代码（SDK格式如 ["851426.SI"]），不传则从 PhoenixA 获取全部
    """

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

        self._info_data = ad.InfoData()

    def execute(self, ctx):
        from artemis.core.config_manager import cfg_mgr

        task_engine_cfg = cfg_mgr.task_engine_config()
        cache_dir = os.path.abspath(task_engine_cfg.amazing_data_cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        code_list = _resolve_index_codes(ctx)

        try:
            result = self._info_data.get_industry_constituent(code_list, local_path=cache_dir, is_local=False)
            return result
        except Exception as e:
            ctx.fail(f"fetch SWHY industry constituent failed: {e}", phase='execute')
            return {}

    def post_process(self, ctx: TaskContext, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        processed = []
        seen = set()
        for code, df in result.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for _, row in df.iterrows():
                con_code = str(row.get("CON_CODE", "")).strip()
                symbol = con_code.split(".")[0] if "." in con_code else con_code
                index_code = str(row.get("INDEX_CODE", code))
                key = (index_code, symbol)
                if key in seen:
                    continue
                seen.add(key)
                processed.append({
                    "index_code": index_code,
                    "con_code": con_code,
                    "symbol": symbol,
                    "indate": str(row.get("INDATE", "")),
                    "outdate": str(row.get("OUTDATE", "")),
                    "index_name": str(row.get("INDEX_NAME", "")),
                })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': 'swhy_constituent_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        from artemis.consts import Taxonomy

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = phoenixA_client.upsert_industry_constituents(
            processed,
            consts.DataSource.DS_AMAZING_DATA.value,
            taxonomy=Taxonomy.SWHY.value,
            market="zh_a",
            run_id=ctx.run_id,
        )
        if ok is False:
            ctx.fail("failed to sink SWHY industry constituents to phoenixA", phase='sink')

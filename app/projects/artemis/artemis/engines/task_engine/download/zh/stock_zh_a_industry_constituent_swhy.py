import os
from typing import Any, Dict, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.download.zh.utils import get_symbols_from_params


class StockZHAIndustryConstituentSWHY(WorkerUnit):
    """下载申万行业指数成分股数据（来源：AmazingData InfoData get_industry_constituent）。

    SDK参数支持（per AmazingData_development_guide.md V1.0.24）：
      get_industry_constituent(code_list, local_path, is_local)
      - code_list: 行业指数代码列表（来自 get_industry_base_info）
      - 注意：此接口不支持 begin_date/end_date

    ctx.params:
      - symbols: list[str]  — 行业指数代码列表（可选，不传则从 PhoenixA 获取全部股票代码）
    """

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params or {}
        symbols = params.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            ctx.fail(f"symbols must be a list, got {type(symbols).__name__}", phase='parameter_check')
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


        # Resolve code_list: explicit symbols or fallback to PhoenixA
        explicit_symbols = get_symbols_from_params(ctx)
        if explicit_symbols is not None:
            code_list = explicit_symbols
        else:
            phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
            securities = phoenixA_client.get_securities(asset_type="stock", market="zh_a")
            code_list = list(securities.keys())

        try:
            result = self._info_data.get_industry_constituent(code_list, local_path=cache_dir, is_local=False)
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
                con_code = str(row.get("CON_CODE", "")).strip()
                # Extract pure symbol from con_code (e.g. "603648.SH" → "603648")
                symbol = con_code.split(".")[0] if "." in con_code else con_code
                processed.append({
                    "index_code": str(row.get("INDEX_CODE", code)),
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


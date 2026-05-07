import os
from typing import Any, Dict, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.download.zh.utils import get_symbols_from_params, get_sdk_date_kwargs


class StockZHAIndustryDailySWHY(WorkerUnit):
    """下载申万行业指数日行情数据（来源：AmazingData InfoData get_industry_daily）。

    SDK参数支持（per AmazingData_development_guide.md V1.0.24）：
      get_industry_daily(code_list, local_path, is_local, begin_date?, end_date?)
      - code_list: 行业指数代码列表（来自 get_industry_base_info）
      - begin_date/end_date: 交易日期（可选）

    ctx.params:
      - symbols: list[str]  — 行业指数代码列表
      - start_date: int/str  — 交易日期起始（映射到 SDK begin_date）
      - end_date: int/str    — 交易日期结束（映射到 SDK end_date）
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

        # Convert start_date/end_date → SDK begin_date/end_date
        sdk_date_kwargs = get_sdk_date_kwargs(ctx)

        try:
            result = self._info_data.get_industry_daily(
                code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs
            )
            return result
        except Exception as e:
            ctx.fail(f"fetch SWHY industry daily failed: {e}", phase='execute')
            return {}

    def post_process(self, ctx: TaskContext, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        processed = []
        for code, df in result.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for _, row in df.iterrows():
                processed.append({
                    "index_code": str(row.get("INDEX_CODE", code)),
                    "trade_date": str(row.get("TRADE_DATE", "")),
                    "open": float(row.get("OPEN", 0.0)),
                    "high": float(row.get("HIGH", 0.0)),
                    "close": float(row.get("CLOSE", 0.0)),
                    "low": float(row.get("LOW", 0.0)),
                    "pre_close": float(row.get("PRE_CLOSE", 0.0)),
                    "amount": float(row.get("AMOUNT", 0.0)),
                    "volume": float(row.get("VOLUME", 0.0)),
                    "pb": float(row.get("PB", 0.0)),
                    "pe": float(row.get("PE", 0.0)),
                    "total_cap": float(row.get("TOTAL_CAP", 0.0)),
                    "a_float_cap": float(row.get("A_FLOAT_CAP", 0.0)),
                })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': 'swhy_industry_daily_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        from artemis.consts import Taxonomy

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = phoenixA_client.upsert_industry_daily(
            processed,
            consts.DataSource.DS_AMAZING_DATA.value,
            taxonomy=Taxonomy.SWHY.value,
            market="zh_a",
            run_id=ctx.run_id,
        )
        if ok is False:
            ctx.fail("failed to sink SWHY industry daily to phoenixA", phase='sink')


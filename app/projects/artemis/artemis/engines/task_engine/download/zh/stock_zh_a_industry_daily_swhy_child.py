import os
from typing import Any, Dict, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices, Taxonomy
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.download.zh.utils import get_sdk_date_kwargs


class StockZHAIndustryDailySWHYChild(WorkerUnit):
    """下载单个申万行业指数的日行情数据（OHLCV、PE、PB、市值等）。"""

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

        params = ctx.params or {}
        index_code = params.get("index_code")
        if not index_code:
            ctx.fail("missing index_code", phase='execute')
            return {}

        task_engine_cfg = cfg_mgr.task_engine_config()
        cache_dir = os.path.abspath(task_engine_cfg.amazing_data_cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        sdk_date_kwargs = get_sdk_date_kwargs(ctx)

        try:
            result = self._info_data.get_industry_daily(
                [index_code], local_path=cache_dir, is_local=False, **sdk_date_kwargs
            )
            return result
        except Exception as e:
            ctx.fail(f"fetch SWHY industry daily for {index_code} failed: {e}", phase='execute')
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
            ctx.logger.info({'event': 'swhy_daily_child_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
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

import math
import os
from typing import Any, Dict, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices, Taxonomy
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.download.zh.utils import get_sdk_date_kwargs


def _safe_float(val, default=0.0):
    """Convert to float, replacing nan/inf with default (JSON-compliant)."""
    try:
        f = float(val)
        if not math.isfinite(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


class StockZHAIndustryWeightSWHYChild(WorkerUnit):
    """下载单个申万行业指数的成分股日权重数据。"""

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
            result = self._info_data.get_industry_weight(
                [index_code], local_path=cache_dir, is_local=False, **sdk_date_kwargs
            )
            return result
        except Exception as e:
            ctx.fail(f"fetch SWHY industry weight for {index_code} failed: {e}", phase='execute')
            return {}

    def post_process(self, ctx: TaskContext, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        processed = []
        for code, df in result.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                ctx.logger.info({
                    'event': 'swhy_weight_post_process_skip',
                    'code': code,
                    'type': type(df).__name__,
                    'empty': getattr(df, 'empty', True),
                    'run_id': ctx.run_id,
                })
                continue
            for _, row in df.iterrows():
                con_code = str(row.get("CON_CODE", "")).strip()
                symbol = con_code.split(".")[0] if "." in con_code else con_code
                raw_td = str(row.get("TRADE_DATE", ""))
                if len(raw_td) == 8 and raw_td.isdigit():
                    trade_date = f"{raw_td[:4]}-{raw_td[4:6]}-{raw_td[6:8]}"
                else:
                    trade_date = raw_td
                processed.append({
                    "index_code": str(row.get("INDEX_CODE", code)),
                    "con_code": con_code,
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "weight": _safe_float(row.get("WEIGHT")),
                })
        ctx.logger.info({
            'event': 'swhy_weight_post_process_result',
            'processed_count': len(processed),
            'run_id': ctx.run_id,
        })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': 'swhy_weight_child_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        from artemis.consts import Taxonomy

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = phoenixA_client.upsert_industry_weights(
            processed,
            consts.DataSource.DS_AMAZING_DATA.value,
            taxonomy=Taxonomy.SWHY.value,
            market="zh_a",
            run_id=ctx.run_id,
        )
        if ok is False:
            ctx.fail("failed to sink SWHY industry weights to phoenixA", phase='sink')

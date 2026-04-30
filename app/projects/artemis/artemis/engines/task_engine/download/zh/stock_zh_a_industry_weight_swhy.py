import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


def _parse_date_to_int(date_str: Optional[str]) -> Optional[int]:
    """Convert 'YYYY-MM-DD' to int YYYYMMDD for SDK."""
    if not date_str:
        return None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return int(date_str.replace("-", ""))
    except ValueError:
        return None


class StockZHAIndustryWeightSWHY(WorkerUnit):
    """下载申万行业指数成分股日权重数据（来源：AmazingData InfoData get_industry_weight）。"""

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params or {}
        # symbols, start_date, end_date are all optional
        symbols = params.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            ctx.fail(f"symbols must be a list, got {type(symbols).__name__}", phase='parameter_check')
            return
        for d in ("start_date", "end_date"):
            val = params.get(d)
            if val is not None:
                try:
                    datetime.strptime(str(val), "%Y-%m-%d")
                except ValueError:
                    ctx.fail(f"{d} must be YYYY-MM-DD format, got '{val}'", phase='parameter_check')
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

        params = ctx.params or {}

        # Resolve code_list: cronjob > task.yaml > fallback to PhoenixA
        symbols = params.get("symbols")
        if symbols:
            code_list = symbols
        else:
            phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
            securities = phoenixA_client.get_securities(asset_type="stock", market="zh_a")
            code_list = list(securities.keys())

        # Build SDK kwargs
        sdk_kwargs: Dict[str, Any] = {"local_path": cache_dir, "is_local": False}
        begin_date = _parse_date_to_int(params.get("start_date"))
        end_date = _parse_date_to_int(params.get("end_date"))
        if begin_date is not None:
            sdk_kwargs["begin_date"] = begin_date
        if end_date is not None:
            sdk_kwargs["end_date"] = end_date

        try:
            result = self._info_data.get_industry_weight(code_list, **sdk_kwargs)
            return result
        except Exception as e:
            ctx.fail(f"fetch SWHY industry weight failed: {e}", phase='execute')
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
                    "trade_date": str(row.get("TRADE_DATE", "")),
                    "weight": float(row.get("WEIGHT", 0.0)),
                })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': 'swhy_weight_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = phoenixA_client.upsert_industry_weights(
            processed, consts.DataSource.DS_AMAZING_DATA.value, ctx.run_id
        )
        if ok is False:
            ctx.fail("failed to sink SWHY industry weights to phoenixA", phase='sink')


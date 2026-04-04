from typing import Any, Dict

import pandas as pd
from akshare import stock_bj_a_spot_em, stock_sz_a_spot_em, stock_sh_a_spot_em

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


# 根据 exchange 选择对应的 security_type
security_type_map = {
    "SH": "SH_A",
    "SZ": "SZ_A",
    "BJ": "BJ_A",
    "ALL": "EXTRA_STOCK_A"
}

class StockZHAList(WorkerUnit):
    """单任务：每日刷新 A 股列表（上交所/深交所）。

    参数约定（ctx.params 最终形态）：
      - exchange: str, "SH" 或 "SZ"，用于决定调用哪个 akshare 接口

    行为：
      - 根据 exchange 调用 ak.stock_sh_a_spot_em 或 ak.stock_sz_a_spot_em
      - 只保留股票名称、股票代码两列
      - 不做真实下游写入，sink 中打印/打日志记录数量与示例
    """

    VALID_EXCHANGES = {"SH", "SZ", "BJ","ALL"}

    # ------- 参数检查 -------

    def parameter_check(self, ctx):
        params = ctx.incoming_params or {}
        exchange = params.get("exchange")
        if not exchange:
            ctx.fail("missing required param: exchange (SH/SZ/BJ/ALL)", phase='parameter_check')
            return
        if exchange not in self.VALID_EXCHANGES:
            ctx.fail(f"invalid exchange: {exchange}, expected one of {sorted(self.VALID_EXCHANGES)}", phase='parameter_check')
            return

    # ------- 动态参数 -------

    def load_dynamic_parameters(self, ctx) -> Dict[str, Any]:
        # 本任务目前无外部动态依赖，返回空 dict 即可
        return {}

    def before_execute(self, ctx: TaskContext) -> None:
        from artemis.core.sdk.manager import sdk_mgr
        from artemis.consts import SDK_NAME

        try:
            am_object = sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
        except Exception as e:
            # 获取 SDK 失败 — 标记任务失败或记录
            ctx.fail(f"failed to acquire AmazingData SDK: {e}", phase='before_execute')
            return
        ctx.params["am_object"] = am_object

    # ------- 执行主逻辑 -------

    def execute(self, ctx):
        params = ctx.params or {}
        am_object = params.get("am_object")
        exchange = params.get("exchange")

        security_type = security_type_map.get(exchange, "EXTRA_STOCK_A")
        code_info = am_object.get_code_info(security_type=security_type)

        sub_df = code_info[["symbol"]].copy()
        sub_df.index.name = "code"
        sub_df = sub_df.reset_index()
        sub_df.columns = ["code", "company"]
        # derive exchange from the original symbol suffix (e.g. '301301.SZ' -> 'SZ')
        sub_df["exchange"] = sub_df["code"].str.split(".").str[-1]
        # remove suffix from code so downstream receives plain code like '301301'
        sub_df["code"] = sub_df["code"].str.split(".").str[0]
        if exchange != "ALL":
            sub_df = sub_df[sub_df["exchange"] == exchange]
        rows = sub_df.to_dict(orient="records")
        return {
            "exchange": exchange,
            "rows": rows,
            "count": len(rows),
        }

    # ------- 下游写入（仅打印/日志） -------

    def sink(self, ctx, processed: Dict[str, Any]):
        exchange = processed.get("exchange")
        count = processed.get("count", 0)
        rows = processed.get("rows") or []
        sample = rows[:3]
        ctx.logger.info({
            "event": "stock_a_list_daily_sink",
            "exchange": exchange,
            "count": count,
            "sample": sample,
            "run_id": ctx.run_id,
        })

        ctx.stats["exchange"] = exchange
        ctx.stats["row_count"] = int(count or 0)

        client = ctx.dept_http.get(DeptServices.PHOENIXA)
        ok = client.stock_zh_a_list_batch_upsert(rows, ctx.run_id)
        if ok is False:
            ctx.fail(f"failed to sink stock list to phoenixA for exchange={exchange}", phase='sink')
            return


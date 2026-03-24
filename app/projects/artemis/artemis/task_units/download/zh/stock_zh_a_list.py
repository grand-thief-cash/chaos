from typing import Any, Dict

import pandas as pd
from akshare import stock_bj_a_spot_em, stock_sz_a_spot_em, stock_sh_a_spot_em

from artemis.consts import DeptServices
from artemis.task_units.worker_unit import WorkerUnit


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
        inc = ctx.incoming_params or {}
        exchange = inc.get("exchange")
        if not exchange:
            ctx.fail("missing required param: exchange (SH/SZ)", phase='parameter_check')
            return
        if exchange not in self.VALID_EXCHANGES:
            ctx.fail(f"invalid exchange: {exchange}, expected one of {sorted(self.VALID_EXCHANGES)}", phase='parameter_check')
            return

    # ------- 动态参数 -------

    def load_dynamic_parameters(self, ctx) -> Dict[str, Any]:
        # 本任务目前无外部动态依赖，返回空 dict 即可
        return {}

    # ------- 执行主逻辑 -------

    def execute(self, ctx):
        params = ctx.params or {}
        exchange = params.get("exchange")


        if exchange == "SH":
            df = stock_sh_a_spot_em()
        elif exchange == "SZ":
            df = stock_sz_a_spot_em()
        elif exchange == "BJ":
            df = stock_bj_a_spot_em()
        elif exchange == "ALL":
            df_sh = stock_sh_a_spot_em()
            df_sz = stock_sz_a_spot_em()
            df_bj = stock_bj_a_spot_em()
            df = pd.concat([df_sh, df_sz, df_bj], ignore_index=True)
        else:
            df = pd.DataFrame()
            ctx.fail(f"{exchange} is not supported exchange", phase='execute')
            return {
                "exchange": exchange,
                "rows": [],
                "count": 0,
            }



        sub_df = df[["代码", "名称"]]
        sub_df.columns = ["code", "company"]
        # 增加交易所列，值与传入的 exchange 一致
        sub_df["exchange"] = exchange
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


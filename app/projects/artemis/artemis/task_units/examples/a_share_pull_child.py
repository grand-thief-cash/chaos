from datetime import datetime, timedelta
from typing import Any, Dict

from artemis.task_units.base import BaseTaskUnit


class ASharePullChildTask(BaseTaskUnit):
    """Child task: 拉取单个 symbol 的历史数据并写入下游。

    参数约定（ctx.params 最终形态）：
      - symbol: str  由 parent fan_out 时指定
      - period: str  由 parent 传入（同时参与 task.yaml variant 匹配）
      - adjust: str
      - start_date: str (YYYYMMDD) 由子任务根据 task.yaml 配置和 last_updates 自行计算
      - end_date: str (YYYYMMDD)   优先使用 parent 传下来的统一 end_date；若无则默认今天
      - sink: dict { url: str }

    注意：
      - start_date 的计算逻辑：
          base_start = task.yaml 中配置的 start_date (字符串 YYYYMMDD)
          last_update = last_updates[symbol] (如果有)
          effective_start = max(base_start, last_update) + 1 day
      - 上述计算应在子任务内部完成，而不是由 parent 计算。
    """

    # ------- 参数与动态配置 -------

    def parameter_check(self, ctx):
        inc = ctx.incoming_params or {}
        if not inc.get("symbol"):
            raise ValueError("missing required param: symbol")
        if not inc.get("period"):
            raise ValueError("missing required param: period")
        # adjust / sink / last_updates 可选

    def load_dynamic_parameters(self, ctx) -> Dict[str, Any]:
        """根据 task.yaml 配置与 last_updates 计算 start/end_date。

        这里会：
        - 从 task_default / task_variant 中拿到 start_date 默认值（通过 BaseTaskUnit.merge_parameters）。
        - 使用 incoming_params 里的 last_updates[symbol] 计算最终的 start_date。
        实现方式：
        - 先调用基类 merge_parameters 把默认配置与 incoming 合并后再做覆盖，
          因为 BaseTaskUnit.run 的顺序是：load_dynamic_parameters -> merge_parameters。
        所以这里返回的是只包含 date 相关键的动态参数，供 merge_parameters 合并。
        """
        inc = ctx.incoming_params or {}
        symbol = inc.get("symbol")
        last_updates: Dict[str, str] = inc.get("last_updates") or {}

        # 获取 last_update（可能为空）
        last_update_str = last_updates.get(symbol)

        # 从 task.yaml default 中读取 start_date 需要在 merge_parameters 之后才能拿到，
        # 但当前阶段还没 merge；所以我们只负责根据 last_update 先准备一个覆盖字段，
        # 真正的 base_start 由配置合并完成后再在 execute 中做最终确定。
        #
        # 这里的策略：
        # - 动态阶段只把 last_update 透传到 params，供 execute 使用。
        return {"_symbol_last_update": last_update_str}

    # ------- 执行主逻辑 -------

    def execute(self, ctx):
        params = ctx.params
        symbol = params.get("symbol")
        period = params.get("period", "daily")
        adjust = params.get("adjust", "")

        # 1) 从配置中拿默认 start_date（必须在 task.yaml 的 task_defaults 或 variants 中提供）
        base_start_str = params.get("start_date")
        if not base_start_str:
            raise ValueError("start_date must be provided by task config (task.yaml)")

        try:
            base_start = datetime.strptime(base_start_str, "%Y%m%d").date()
        except Exception as e:
            raise ValueError(f"invalid start_date in config: {base_start_str}") from e

        # 2) 根据 last_update 计算 effective_start
        lu_str = params.get("_symbol_last_update")
        if lu_str:
            try:
                lu_date = datetime.strptime(lu_str, "%Y%m%d").date()
                start_date = max(base_start, lu_date) + timedelta(days=1)
            except Exception as e:
                raise ValueError(f"invalid last_update for symbol {symbol}: {lu_str}") from e
        else:
            start_date = base_start

        # 3) end_date：优先使用 parent 传下来的统一 end_date；否则使用今天
        end_date_str = params.get("end_date")
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y%m%d").date()
            except Exception as e:
                raise ValueError(f"invalid end_date from parent: {end_date_str}") from e
        else:
            end_date = datetime.utcnow().date()
            end_date_str = end_date.strftime("%Y%m%d")

        start_date_str = start_date.strftime("%Y%m%d")

        # 把最终运行参数记录回 ctx.params，方便 sink 与下游调试
        ctx.params["start_date"] = start_date_str
        ctx.params["end_date"] = end_date_str

        # Validate dates format
        for name, val in [("start_date", start_date_str), ("end_date", end_date_str)]:
            try:
                datetime.strptime(val, "%Y%m%d")
            except Exception:
                raise ValueError(f"{name} must be YYYYMMDD, got {val}")

        # 4) 调用 akshare（若不可用则 mock）
        try:
            import akshare as ak  # type: ignore

            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date_str,
                end_date=end_date_str,
                adjust=adjust,
            )
            result = {
                "symbol": symbol,
                "period": period,
                "adjust": adjust,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "count": int(len(df)) if hasattr(df, "__len__") else 0,
            }
        except Exception as e:  # pragma: no cover - 依赖外部库
            if ctx.logger:
                ctx.logger.warning(
                    {
                        "event": "akshare_unavailable",
                        "error": str(e),
                        "symbol": symbol,
                        "run_id": ctx.run_id,
                    }
                )
            result = {
                "symbol": symbol,
                "period": period,
                "adjust": adjust,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "count": 42,
                "mock": True,
            }
        return result

    # ------- 下游写入 -------

    def sink(self, ctx, processed: Dict[str, Any]):
        # Mock external sink: just log what would be sent
        sink_cfg = (ctx.params or {}).get("sink") or {}
        url = sink_cfg.get("url", "http://mock-sink.local/ingest")
        payload = {
            "symbol": processed.get("symbol"),
            "period": processed.get("period"),
            "adjust": processed.get("adjust"),
            "date_range": {
                "from": processed.get("start_date"),
                "to": processed.get("end_date"),
            },
            "count": processed.get("count"),
            "mock": processed.get("mock", False),
            "meta": {
                "parent_run_id": (ctx.incoming_params.get("_meta") or {}).get("parent_run_id"),
                "run_id": ctx.run_id,
            },
        }
        if ctx.logger:
            ctx.logger.info(
                {
                    "event": "sink_send",
                    "url": url,
                    "payload_summary": {
                        "symbol": payload["symbol"],
                        "period": payload["period"],
                        "adjust": payload["adjust"],
                        "count": payload["count"],
                    },
                    "run_id": ctx.run_id,
                }
            )
        ctx.stats["sink_url"] = url
        ctx.stats["rows_sent"] = payload["count"]

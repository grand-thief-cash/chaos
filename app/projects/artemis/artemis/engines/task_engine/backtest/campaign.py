from __future__ import annotations

from itertools import product
from typing import Any, Dict, List

from artemis.engines.strategy_engine import analyzer_profile_registry, data_provider_registry, strategy_registry
from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit

MAX_SYMBOLS = 50
MAX_CHILDREN = 200


class BacktraderCampaignTask(OrchestratorUnit):
    """回测战役编排任务，负责将多股票多参数组合的回测拆分为并行的子任务执行。

    生命周期：parameter_check → before_execute -> load_dynamic_parameters -> plan -> finalize。
    Campaign 会将 N 只股票 × M 组参数组合拆分为 N*M 个 BacktraderRunTask 子任务。
    """
    def parameter_check(self, ctx: TaskContext):
        """校验必填参数（策略、数据源、分析器、股票代码、日期范围等)的有效性。"""
        params = ctx.incoming_params
        required = [
            "mode",
            "strategy_code",
            "data_provider_code",
            "analyzer_profile",
            "period",
            "start_date",
            "end_date",
        ]
        missing = [key for key in required if not params.get(key)]
        if missing:
            ctx.fail(f"missing required params: {', '.join(missing)}", phase="parameter_check")
            return

        mode = params.get("mode")
        if mode != "historical":
            ctx.fail("Phase 1 only supports mode=historical", phase="parameter_check")
            return

        strategy_code = str(params.get("strategy_code") or "").strip()
        data_provider_code = str(params.get("data_provider_code") or "").strip()
        analyzer_profile = str(params.get("analyzer_profile") or "").strip()
        start_date = str(params.get("start_date") or "").strip()
        end_date = str(params.get("end_date") or "").strip()
        symbols = params.get("symbols") or []
        universe_code = str(params.get("universe_code") or "").strip()

        if not strategy_registry.has(strategy_code):
            ctx.fail(f"strategy_code '{strategy_code}' is not registered", phase="parameter_check")
            return
        if not data_provider_registry.get(data_provider_code):
            ctx.fail(f"data_provider_code '{data_provider_code}' is not registered", phase="parameter_check")
            return
        if not analyzer_profile_registry.get(analyzer_profile):
            ctx.fail(f"analyzer_profile '{analyzer_profile}' is not registered", phase="parameter_check")
            return
        if not symbols and not universe_code:
            ctx.fail("symbols or universe_code is required", phase="parameter_check")
            return
        if start_date > end_date:
            ctx.fail("start_date must be <= end_date", phase="parameter_check")
            return

        if symbols and len(symbols) > MAX_SYMBOLS:
            ctx.fail(f"too many symbols ({len(symbols)}), max {MAX_SYMBOLS}", phase="parameter_check")
            return

        parameter_grid = params.get("parameter_grid")
        strategy_params = params.get("strategy_params")
        if parameter_grid is not None and not isinstance(parameter_grid, list):
            ctx.fail("parameter_grid must be a list", phase="parameter_check")
            return
        if strategy_params is not None and not isinstance(strategy_params, dict):
            ctx.fail("strategy_params must be a dict", phase="parameter_check")
            return

        # Estimate total children to prevent unbounded expansion
        symbol_count = len(symbols) if symbols else MAX_SYMBOLS
        param_set_count = len(parameter_grid) if parameter_grid else 1
        estimated_children = symbol_count * param_set_count
        if estimated_children > MAX_CHILDREN:
            ctx.fail(
                f"estimated child tasks ({estimated_children}) exceeds max ({MAX_CHILDREN}), reduce symbols or parameter_grid",
                phase="parameter_check",
            )
            return

    def before_execute(self, ctx: TaskContext):
        return

    def load_dynamic_parameters(self, ctx: TaskContext) -> Dict[str, Any]:
        """动态加载股票代码，验证数据可用性，解析 universe_code。"""
        params = ctx.params
        phoenix_client: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        requested_symbols = [str(s).strip() for s in (params.get("symbols") or []) if str(s).strip()]

        # Resolve universe_code if no explicit symbols provided
        code_infos = None
        if not requested_symbols:
            universe_code = str(params.get("universe_code") or "").strip()
            if universe_code:
                if universe_code.upper() == "ALL":
                    code_infos = phoenix_client.get_stock_zh_a_codes()
                    requested_symbols = list(code_infos.keys())
                else:
                    ctx.fail(f"universe_code '{universe_code}' is not supported in Phase 1", phase="load_dynamic_parameters")
                    return {}
            else:
                ctx.fail("symbols or universe_code is required", phase="load_dynamic_parameters")
                return {}

        # Verify symbols exist in PhoenixA (skip redundant call if already fetched via universe_code=ALL)
        if code_infos is None:
            code_infos = phoenix_client.get_stock_zh_a_codes(codes=requested_symbols)
        available_symbols = [code for code in requested_symbols if code in code_infos]
        if not available_symbols:
            ctx.fail("no valid symbols found in PhoenixA", phase="load_dynamic_parameters")
            return {}

        # Check data availability
        last_updates = phoenix_client.get_stock_zh_a_last_updates(
            period=params.get("timeframe", "daily"),
            adjust=params.get("adjust", "nf"),
            codes=available_symbols,
        )
        symbols_with_data = [s for s in available_symbols if last_updates.get(s)]
        if not symbols_with_data:
            ctx.fail("no resolved symbols have historical data in PhoenixA", phase="load_dynamic_parameters")
            return {}

        ctx.params["resolved_symbols"] = symbols_with_data
        ctx.params["code_infos"] = code_infos
        return {"resolved_symbols": symbols_with_data}

    def _normalize_parameter_sets(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """将 parameter_grid 或 strategy_params 归一化为统一的参数集合列表。"""
        params = ctx.params
        parameter_grid = params.get("parameter_grid")
        if isinstance(parameter_grid, list) and parameter_grid:
            normalized: List[Dict[str, Any]] = []
            for item in parameter_grid:
                if not isinstance(item, dict):
                    raise ValueError("parameter_grid items must be dict")
                normalized.append(item)
            return normalized
        base_params = params.get("strategy_params") or {}
        if not isinstance(base_params, dict):
            raise ValueError("strategy_params must be dict")
        return [base_params]

    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """生成子任务列表，每个子任务 = 1 只股票 × 1 组策略参数。"""
        symbols = ctx.params.get("resolved_symbols") or []
        strategy_param_sets = self._normalize_parameter_sets(ctx)
        child_specs: List[Dict[str, Any]] = []

        for symbol, strategy_params in product(symbols, strategy_param_sets):
            child_specs.append(
                {
                    "key": TaskCode.BACKTRADER_RUN,
                    "params": {
                        "mode": ctx.params.get("mode"),
                        "market": ctx.params.get("market"),
                        "period": ctx.params.get("period"),
                        "adjust": ctx.params.get("adjust"),
                        "strategy_code": ctx.params.get("strategy_code"),
                        "data_provider_code": ctx.params.get("data_provider_code"),
                        "analyzer_profile": ctx.params.get("analyzer_profile"),
                        "cash": ctx.params.get("cash"),
                        "commission": ctx.params.get("commission"),
                        "persist_artifacts": ctx.params.get("persist_artifacts") or [],
                        "symbol": symbol,
                        "start_date": ctx.params.get("start_date"),
                        "end_date": ctx.params.get("end_date"),
                        "strategy_params": strategy_params,
                    },
                }
            )

        if len(child_specs) > MAX_CHILDREN:
            raise ValueError(f"too many child tasks ({len(child_specs)}), max {MAX_CHILDREN}")

        return child_specs

    def finalize(self, ctx: TaskContext):
        """汇总子任务统计信息（总数、完成数、成功率等)。"""
        children_total = int(getattr(ctx, "children_total", 0) or 0)
        children_completed = int(getattr(ctx, "children_completed", 0) or 0)
        ctx.stats["children_total"] = children_total
        ctx.stats["children_completed"] = children_completed
        ctx.stats["success_count"] = children_completed
        # fail-fast: if any child fails, parent fails before reaching finalize
        ctx.stats["failed_count"] = 0
        ctx.stats["campaign_mode"] = ctx.params.get("mode")


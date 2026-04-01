from __future__ import annotations

from itertools import product
from typing import Any, Dict, List

from artemis.backtrader import analyzer_profile_registry, data_provider_registry, strategy_registry
from artemis.consts import DeptServices, TaskCode
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.task_units.orchestrator_unit import OrchestratorUnit


class BacktraderCampaignTask(OrchestratorUnit):
    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params
        required = [
            "mode",
            "strategy_code",
            "data_provider_code",
            "analyzer_profile",
            "timeframe",
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
        if not start_date or not end_date:
            ctx.fail("start_date and end_date are required", phase="parameter_check")
            return
        if start_date > end_date:
            ctx.fail("start_date must be <= end_date", phase="parameter_check")
            return

        parameter_grid = params.get("parameter_grid")
        strategy_params = params.get("strategy_params")
        if parameter_grid is not None and not isinstance(parameter_grid, list):
            ctx.fail("parameter_grid must be a list", phase="parameter_check")
            return
        if strategy_params is not None and not isinstance(strategy_params, dict):
            ctx.fail("strategy_params must be a dict", phase="parameter_check")
            return

    def before_execute(self, ctx: TaskContext):
        return

    def load_dynamic_parameters(self, ctx: TaskContext) -> Dict[str, Any]:
        params = ctx.params
        phoenix_client: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        requested_symbols = [str(s).strip() for s in (params.get("symbols") or []) if str(s).strip()]
        if not requested_symbols:
            universe_code = str(params.get("universe_code") or "").strip()
            if universe_code:
                # Phase 1 minimal support: treat ALL as stock list fetch from PhoenixA.
                if universe_code.upper() == "ALL":
                    requested_symbols = list(phoenix_client.get_stock_zh_a_codes().keys())
                else:
                    ctx.fail(f"universe_code '{universe_code}' is not supported in Phase 1", phase="load_dynamic_parameters")
                    return {}

        code_infos = phoenix_client.get_stock_zh_a_codes(codes=requested_symbols or None)
        available_symbols = [code for code in requested_symbols if code in code_infos]
        if not available_symbols:
            ctx.fail("no valid symbols found in PhoenixA", phase="load_dynamic_parameters")
            return {}

        ctx.params["resolved_symbols"] = available_symbols
        ctx.params["code_infos"] = code_infos
        return {"resolved_symbols": available_symbols}

    def _normalize_parameter_sets(self, ctx: TaskContext) -> List[Dict[str, Any]]:
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
                        "timeframe": ctx.params.get("timeframe"),
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
        return child_specs

    def finalize(self, ctx: TaskContext):
        children_total = int(getattr(ctx, "children_total", 0) or 0)
        children_completed = int(getattr(ctx, "children_completed", 0) or 0)
        ctx.stats["children_total"] = children_total
        ctx.stats["children_completed"] = children_completed
        ctx.stats["success_count"] = children_completed
        ctx.stats["failed_count"] = max(children_total - children_completed, 0)
        ctx.stats["campaign_mode"] = ctx.params.get("mode")


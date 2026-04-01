from __future__ import annotations

import json
from typing import Any, Dict, List

import pandas as pd

from artemis.backtrader import analyzer_profile_registry, data_provider_registry, strategy_registry
from artemis.backtrader.engine_builder import BacktraderEngineBuilder
from artemis.backtrader.result_normalizer import BacktestResultNormalizer
from artemis.consts import DeptServices, TaskStatus
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.task_units.worker_unit import WorkerUnit


class BacktraderRunTask(WorkerUnit):
    @staticmethod
    def _extract_analyzer_results(strategy_instance: Any) -> Dict[str, Any]:
        analyzers = getattr(strategy_instance, "analyzers", None)
        if analyzers is None:
            return {}
        try:
            items = analyzers.getitems()
        except Exception:
            return {}
        return {name: analyzer.get_analysis() for name, analyzer in items}

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params
        required = [
            "mode",
            "strategy_code",
            "data_provider_code",
            "analyzer_profile",
            "symbol",
            "timeframe",
            "start_date",
            "end_date",
        ]
        missing = [key for key in required if not params.get(key)]
        if missing:
            ctx.fail(f"missing required params: {', '.join(missing)}", phase="parameter_check")
            return
        if params.get("mode") != "historical":
            ctx.fail("Phase 1 only supports historical mode", phase="parameter_check")
            return
        strategy_code = str(params.get("strategy_code") or "").strip()
        if not strategy_registry.has(strategy_code):
            ctx.fail(f"strategy_code '{strategy_code}' is not registered", phase="parameter_check")
            return
        provider_code = str(params.get("data_provider_code") or "").strip()
        if not data_provider_registry.get(provider_code):
            ctx.fail(f"data_provider_code '{provider_code}' is not registered", phase="parameter_check")
            return
        analyzer_profile = str(params.get("analyzer_profile") or "").strip()
        if not analyzer_profile_registry.get(analyzer_profile):
            ctx.fail(f"analyzer_profile '{analyzer_profile}' is not registered", phase="parameter_check")
            return
        strategy_params = params.get("strategy_params") or {}
        if not isinstance(strategy_params, dict):
            ctx.fail("strategy_params must be dict", phase="parameter_check")
            return
        fast = strategy_params.get("fast")
        slow = strategy_params.get("slow")
        if fast is not None and int(fast) <= 0:
            ctx.fail("strategy_params.fast must be > 0", phase="parameter_check")
            return
        if slow is not None and int(slow) <= 0:
            ctx.fail("strategy_params.slow must be > 0", phase="parameter_check")
            return

    def before_execute(self, ctx: TaskContext):
        params = ctx.params
        ctx.stats["run_meta"] = {
            "strategy_code": params.get("strategy_code"),
            "symbol": params.get("symbol"),
            "timeframe": params.get("timeframe"),
            "mode": params.get("mode"),
        }

    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        params = ctx.params
        phoenix_client: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        provider_spec = data_provider_registry.require(str(params.get("data_provider_code")))
        strategy_spec = strategy_registry.require(str(params.get("strategy_code")))
        analyzer_profile = analyzer_profile_registry.require(str(params.get("analyzer_profile")))
        symbol = str(params.get("symbol"))
        fields = list(provider_spec.required_fields)

        bars = phoenix_client.get_strategy_market_bars(
            symbol=symbol,
            start_date=str(params.get("start_date")),
            end_date=str(params.get("end_date")),
            timeframe=str(params.get("timeframe")),
            adjust=str(params.get("adjust") or provider_spec.default_adjust),
            fields=fields,
        )
        if not bars:
            ctx.fail(f"no historical bars found for symbol={symbol}", phase="execute")
            return {}

        df = pd.DataFrame(bars)
        cerebro = BacktraderEngineBuilder.build(
            df=df,
            strategy_spec=strategy_spec,
            strategy_params={**strategy_spec.default_params, **(params.get("strategy_params") or {})},
            analyzer_profile=analyzer_profile,
            cash=float(params.get("cash") or 100000.0),
            commission=float(params.get("commission") or 0.0),
        )
        start_cash = float(cerebro.broker.get_cash())
        strategies = cerebro.run()
        strategy_instance = strategies[0]
        analyzer_results = self._extract_analyzer_results(strategy_instance)
        end_value = float(cerebro.broker.get_value())
        bars_processed = len(df.index)
        ctx.stats["bars_processed"] = bars_processed
        ctx.stats["symbol"] = symbol
        return {
            "strategy_instance": strategy_instance,
            "analyzer_results": analyzer_results,
            "bars_processed": bars_processed,
            "start_cash": start_cash,
            "end_value": end_value,
        }

    def post_process(self, ctx: TaskContext, result: Dict[str, Any]) -> Dict[str, Any]:
        if ctx.has_failed() or not result:
            return result
        params = ctx.params
        parent_run_id = None
        meta = params.get("_meta") or {}
        if isinstance(meta, dict):
            parent_run_id = meta.get("parent_run_id")
        normalized = BacktestResultNormalizer.normalize(
            run_id=ctx.run_id,
            parent_run_id=parent_run_id,
            task_code=ctx.task_code,
            mode=str(params.get("mode")),
            strategy_code=str(params.get("strategy_code")),
            symbol=str(params.get("symbol")),
            timeframe=str(params.get("timeframe")),
            start_date=str(params.get("start_date")),
            end_date=str(params.get("end_date")),
            start_cash=float(result.get("start_cash") or 0.0),
            end_value=float(result.get("end_value") or 0.0),
            strategy_instance=result["strategy_instance"],
            analyzer_results=result.get("analyzer_results") or {},
            bars_processed=int(result.get("bars_processed") or 0),
        )
        summary = dict(normalized.get("summary") or {})
        artifacts = dict(normalized.get("artifacts") or {})
        ctx.stats["result_summary"] = summary
        ctx.stats["trade_count"] = summary.get("trade_count", 0)
        ctx.stats["orders_count"] = len(artifacts.get("orders") or [])
        ctx.stats["signals_count"] = len(artifacts.get("signals") or [])
        return normalized

    def sink(self, ctx: TaskContext, processed: Dict[str, Any]):
        if ctx.has_failed() or not processed:
            return
        phoenix_client: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]
        summary = dict(processed.get("summary") or {})
        summary.update(
            {
                "status": TaskStatus.SUCCESS.value,
                "error_message": ctx.error,
                "duration_ms": ctx.duration_ms(),
            }
        )
        if not phoenix_client.save_strategy_run_summary(summary, run_id=ctx.run_id):
            ctx.fail(f"failed to save strategy run summary for run_id={ctx.run_id}", phase="sink")
            return

        persist_artifacts = set(ctx.params.get("persist_artifacts") or [])
        artifacts_payload: List[Dict[str, Any]] = []
        for artifact_type, payload in (processed.get("artifacts") or {}).items():
            if persist_artifacts and artifact_type not in persist_artifacts:
                continue
            artifacts_payload.append(
                {
                    "run_id": str(ctx.run_id),
                    "artifact_type": artifact_type,
                    "payload_json": json.dumps(payload, ensure_ascii=False),
                    "payload_version": "v1",
                }
            )
        if artifacts_payload and not phoenix_client.save_strategy_run_artifacts(artifacts_payload, run_id=ctx.run_id):
            ctx.fail(f"failed to save strategy run artifacts for run_id={ctx.run_id}", phase="sink")

    def finalize(self, ctx: TaskContext):
        summary = ((ctx.stats.get("result_summary") or {}) if isinstance(ctx.stats.get("result_summary"), dict) else {})
        ctx.stats["trade_count"] = summary.get("trade_count", ctx.stats.get("trade_count", 0))
        ctx.stats["orders_count"] = ctx.stats.get("orders_count", 0)


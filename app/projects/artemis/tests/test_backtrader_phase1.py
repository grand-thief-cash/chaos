import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import artemis.task_units  # noqa: F401 registers tasks
from artemis.strategy_engine.strategy_registry import strategy_registry
from artemis.consts import DeptServices, TaskStatus, TaskCode
from artemis.core.clients import NoopDeptServiceClient
from artemis.core.context import TaskContext
from artemis.core.task_engine import TaskEngine
from artemis.models.task_req import TaskRunReq


class FakePhoenixABacktestClient(NoopDeptServiceClient):
    def __init__(self):
        self.saved_summaries = []
        self.saved_artifacts = []

    def get_stock_zh_a_codes(self, codes=None):
        requested = codes or ["600000", "000001"]
        return {code: {"code": code, "exchange": "SH"} for code in requested}

    def get_stock_zh_a_last_updates(self, period="daily", adjust="nf", codes=None):
        requested = codes or ["600000", "000001"]
        return {code: "2024-12-31" for code in requested}

    def get_strategy_market_bars(self, *, symbol, start_date, end_date, timeframe="daily", adjust="nf", fields=None):
        start = datetime.strptime(start_date, "%Y-%m-%d")
        bars = []
        for idx in range(40):
            current = start + timedelta(days=idx)
            price = 10 + idx * 0.1
            bars.append(
                {
                    "date": current.strftime("%Y-%m-%d"),
                    "code": symbol,
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.5,
                    "close": price + (0.2 if idx % 5 == 0 else -0.1),
                    "volume": 1000 + idx,
                    "amount": 100000 + idx * 10,
                }
            )
        return bars

    def save_strategy_run_summary(self, payload, run_id=None):
        self.saved_summaries.append((run_id, payload))
        return True

    def save_strategy_run_artifacts(self, payload, run_id=None):
        self.saved_artifacts.append((run_id, payload))
        return True


def build_req(body, task_code=TaskCode.BACKTRADER_CAMPAIGN.value):
    return TaskRunReq.model_validate(
        {
            "meta": {
                "run_id": 101,
                "task_id": 501,
                "exec_type": "SYNC",
                "task_code": task_code,
            },
            "body": body,
        }
    )


class BacktraderPhase1Tests(unittest.TestCase):
    def setUp(self):
        self.fake_phoenix = FakePhoenixABacktestClient()
        self.patcher = patch.object(
            TaskContext,
            "build_dept_http_client",
            lambda ctx, service_name: self.fake_phoenix if service_name == DeptServices.PHOENIXA else NoopDeptServiceClient(),
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)


    def test_backtrader_campaign_runs_and_persists_child_results(self):
        result = TaskEngine().run(
            build_req(
                {
                    "mode": "historical",
                    "market": "CN_A",
                    "timeframe": "daily",
                    "strategy_code": "sma_cross",
                    "data_provider_code": "phoenixa_hist_daily",
                    "analyzer_profile": "default_hist_v1",
                    "symbols": ["600000", "000001"],
                    "start_date": "2024-01-01",
                    "end_date": "2024-02-15",
                    "parameter_grid": [{"fast": 3, "slow": 8}],
                }
            )
        )

        self.assertEqual(result["status"], TaskStatus.SUCCESS.value)
        self.assertEqual(result["stats"]["children_total"], 2)
        self.assertEqual(result["stats"]["children_completed"], 2)
        self.assertEqual(result["stats"]["success_count"], 2)
        self.assertEqual(len(self.fake_phoenix.saved_summaries), 2)
        self.assertEqual(len(self.fake_phoenix.saved_artifacts), 2)

        run_id, summary = self.fake_phoenix.saved_summaries[0]
        self.assertIn(":", str(run_id))
        self.assertEqual(summary["strategy_code"], "sma_cross")
        self.assertEqual(summary["mode"], "historical")
        self.assertEqual(summary["status"], TaskStatus.SUCCESS.value)
        self.assertGreaterEqual(summary["bars_processed"], 1)

        artifact_run_id, artifacts = self.fake_phoenix.saved_artifacts[0]
        self.assertEqual(str(artifact_run_id), str(run_id))
        artifact_types = {item["artifact_type"] for item in artifacts}
        self.assertIn("analyzers", artifact_types)
        self.assertIn("trades", artifact_types)
        self.assertIn("equity_curve", artifact_types)
        self.assertIn("plot_manifest", artifact_types)
        self.assertIn("plot_series", artifact_types)

    def test_strategy_registry_uses_dedicated_registry_map_metadata(self):
        spec = strategy_registry.require("sma_cross")
        self.assertEqual(spec.code, "sma_cross")
        self.assertEqual(spec.default_params, {"fast": 10, "slow": 30, "stake": 1})
        self.assertEqual(spec.supported_modes, ("historical",))
        self.assertEqual(spec.supported_timeframes, ("daily",))
        self.assertEqual(spec.cls.__name__, "SmaCrossStrategy")

    def test_backtrader_run_fails_when_no_bars_returned(self):
        self.fake_phoenix.get_strategy_market_bars = lambda **kwargs: []
        result = TaskEngine().run(
            build_req(
                {
                    "mode": "historical",
                    "market": "CN_A",
                    "timeframe": "daily",
                    "strategy_code": "sma_cross",
                    "data_provider_code": "phoenixa_hist_daily",
                    "analyzer_profile": "default_hist_v1",
                    "symbol": "600000",
                    "start_date": "2024-01-01",
                    "end_date": "2024-02-15",
                    "strategy_params": {"fast": 3, "slow": 8},
                },
                task_code=TaskCode.BACKTRADER_RUN.value,
            )
        )

        self.assertEqual(result["status"], TaskStatus.FAILED.value)
        self.assertEqual(result["stats"]["failed_phase"], "execute")
        self.assertIn("no historical bars found", result["error"])

    def test_backtrader_campaign_fails_fast_when_required_params_are_missing(self):
        result = TaskEngine().run(
            build_req(
                {
                    "mode": "historical",
                    "strategy_code": "sma_cross",
                    "symbols": ["600000"],
                    "start_date": "2024-01-01",
                    "end_date": "2024-02-15",
                    "strategy_params": {"fast": 3, "slow": 8},
                }
            )
        )

        self.assertEqual(result["status"], TaskStatus.FAILED.value)
        self.assertEqual(result["stats"]["failed_phase"], "parameter_check")
        self.assertIn("missing required params", result["error"])
        self.assertIn("data_provider_code", result["error"])
        self.assertIn("analyzer_profile", result["error"])
        self.assertIn("timeframe", result["error"])


if __name__ == "__main__":
    unittest.main()


import unittest
from unittest.mock import patch
from unittest.mock import Mock

from artemis.consts import DeptServices, TaskStatus
from artemis.core import cfg_mgr
from artemis.core.clients import NoopDeptServiceClient
from artemis.core.context import TaskContext
from artemis.core.task_engine import TaskEngine
from artemis.core.task_registry import registry
from artemis.models.task_req import TaskRunReq
from artemis.engines.task_engine.base import BaseTaskUnit
from artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent import StockZhAHistParent
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit


class SoftFailWorker(BaseTaskUnit):
    def execute(self, ctx: TaskContext):
        try:
            raise RuntimeError("soft execute failure")
        except Exception as exc:
            ctx.fail(exc, phase="execute")
            return {"ignored": True}


class SoftFailChild(BaseTaskUnit):
    def execute(self, ctx: TaskContext):
        ctx.fail("child soft failure", phase="execute")
        return None


class SoftFailParent(OrchestratorUnit):
    def plan(self, ctx: TaskContext):
        return [{"key": "__test_soft_fail_child__", "params": {}}]


class FakePhoenixBadLastUpdateClient(NoopDeptServiceClient):
    def get_securities(self, *, symbols=None, asset_type="stock", market="zh_a", exchanges=None, limit=20000):
        return {"600000": {"symbol": "600000", "exchange": "SH"}}

    def get_bars_last_update(self, *, asset_type="stock", market="zh_a", period="daily", adjust="nf", symbols=None):
        return {"600000": "bad-date"}

def build_req(task_code: str) -> TaskRunReq:
    return TaskRunReq.model_validate(
        {
            "meta": {
                "run_id": 1,
                "task_id": 1,
                "exec_type": "SYNC",
                "task_code": task_code,
            },
            "body": {},
        }
    )


class TaskErrorPropagationTests(unittest.TestCase):
    def setUp(self):
        task_map = {
            "__test_soft_fail_worker__": SoftFailWorker,
            "__test_soft_fail_child__": SoftFailChild,
            "__test_soft_fail_parent__": SoftFailParent,
            "__test_hist_parent_bad_update__": StockZhAHistParent,
        }
        self.patchers = [
            patch.object(cfg_mgr, "task_default", lambda task_code: {"start_date": "2024-01-01", "fields": "date,open"} if str(task_code) == "__test_hist_parent_bad_update__" else {}),
            patch.object(cfg_mgr, "task_variant", lambda task_code, incoming_params: {}),
            patch.object(TaskContext, "build_dept_http_client", lambda self, service_name: NoopDeptServiceClient()),
            patch.object(registry, "get_task", lambda task_code: task_map.get(str(task_code))),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.addCleanup(self._cleanup_patchers)

    def _cleanup_patchers(self):
        for patcher in reversed(self.patchers):
            patcher.stop()

    def test_caught_execute_error_is_returned_in_sync_result(self):
        result = TaskEngine().run(build_req("__test_soft_fail_worker__"))

        self.assertEqual(result["status"], TaskStatus.FAILED.value)
        self.assertEqual(result["error"], "soft execute failure")
        self.assertEqual(result["stats"]["failed_phase"], "execute")

    def test_soft_failure_emits_single_framework_failure_log(self):
        logger = Mock()

        with patch("artemis.core.context.get_logger", return_value=logger):
            result = TaskEngine().run(build_req("__test_soft_fail_worker__"))

        self.assertEqual(result["error"], "soft execute failure")

        error_events = [
            call.args[0].get("event")
            for call in logger.error.call_args_list
            if call.args and isinstance(call.args[0], dict)
        ]
        self.assertEqual(error_events, ["task_failed"])

    def test_orchestrator_child_soft_failure_bubbles_to_parent_result(self):
        result = TaskEngine().run(build_req("__test_soft_fail_parent__"))

        self.assertEqual(result["status"], TaskStatus.FAILED.value)
        self.assertEqual(result["error"], "Child task __test_soft_fail_child__ failed at index 0: child soft failure")
        self.assertEqual(result["stats"]["failed_phase"], "execution_loop")
        self.assertEqual(result["stats"]["children_total"], 1)
        self.assertEqual(result["stats"]["children_completed"], 0)

    def test_hist_parent_invalid_last_update_is_not_swallowed(self):
        def build_client(self, service_name):
            if service_name == DeptServices.PHOENIXA:
                return FakePhoenixBadLastUpdateClient()
            return NoopDeptServiceClient()

        with patch.object(TaskContext, "build_dept_http_client", build_client), \
             patch("artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent.bs.login", return_value=type("LoginResult", (), {"error_code": "0"})()), \
             patch("artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent.bs.logout", return_value=None):
            result = TaskEngine().run(
                TaskRunReq.model_validate(
                    {
                        "meta": {
                            "run_id": 1,
                            "task_id": 1,
                            "exec_type": "SYNC",
                            "task_code": "__test_hist_parent_bad_update__",
                        },
                        "body": {"period": "daily", "adjust": "qfq"},
                    }
                )
            )

        self.assertEqual(result["status"], TaskStatus.FAILED.value)
        self.assertEqual(result["stats"]["failed_phase"], "plan")
        self.assertEqual(result["error"], "Invalid last_update format from PhoenixA for symbol=600000: bad-date")


if __name__ == "__main__":
    unittest.main()


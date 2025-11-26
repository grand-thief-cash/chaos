from typing import Any, Dict, List

from artemis.core.context import TaskContext
from artemis.core.task_status import TaskStatus
from .base import BaseTaskUnit


class ParentTaskUnit(BaseTaskUnit):
    def fan_out(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """Return a list of child specs: {'key': str, 'params': dict}"""
        return []

    def run(self, ctx: TaskContext):
        # run parent prework via BaseTaskUnit lifecycle without sink by default
        ctx.set_status(TaskStatus.RUNNING.value)
        if ctx.logger:
            ctx.logger.info({'event': 'task_start', 'task_code': ctx.task_code, 'run_id': ctx.run_id})
        try:
            self.parameter_check(ctx)
            dyn = self.load_dynamic_parameters(ctx)
            self.merge_parameters(ctx, dyn)
            self.before_execute(ctx)
            res = self.execute(ctx)
            processed = self.post_process(ctx, res)
            # parent does not sink; children do
            specs = self.fan_out(ctx)
            ctx.mark_child_total(len(specs))
            for idx, spec in enumerate(specs):
                if ctx.logger:
                    ctx.logger.info({'event': 'child_start', 'child_index': idx, 'child_key': spec.get('key'), 'run_id': ctx.run_id})
                try:
                    # resolve child task by key
                    from artemis.core import task_registry
                    child_cls = task_registry.get(spec.get('key'))
                    if not child_cls:
                        raise ValueError(f"child task '{spec.get('key')}' not registered")
                    child_ctx = TaskContext(spec.get('key'), {**spec.get('params', {}), '_meta': {'parent_run_id': ctx.run_id}})
                    base_logger = ctx.logger
                    if base_logger:
                        child_ctx.set_logger(base_logger)
                    child = child_cls()
                    child.run(child_ctx)
                    ctx.inc_child_completed()
                    if ctx.logger:
                        ctx.logger.info({'event': 'child_success', 'child_index': idx, 'child_key': spec.get('key'), 'run_id': ctx.run_id})
                except Exception as ce:
                    if ctx.logger:
                        ctx.logger.error({'event': 'child_failure', 'child_index': idx, 'child_key': spec.get('key'), 'error': str(ce), 'run_id': ctx.run_id})
                    raise
            ctx.set_status(TaskStatus.SUCCESS.value)
            if ctx.logger:
                ctx.logger.info({'event': 'task_success', 'task_code': ctx.task_code, 'run_id': ctx.run_id})
        except Exception as e:
            ctx.set_status(TaskStatus.FAILED.value)
            ctx.set_error(str(e))
            if ctx.logger:
                ctx.logger.error({'event': 'task_failed', 'task_code': ctx.task_code, 'error': str(e), 'run_id': ctx.run_id})
            raise
        finally:
            ctx.close()

import time
from typing import Any, Dict

from artemis.core.context import TaskContext
from artemis.core.task_status import TaskStatus


class BaseTaskUnit:
    def parameter_check(self, ctx: TaskContext):
        # validate required params; override in child
        pass

    def load_dynamic_parameters(self, ctx: TaskContext) -> Dict[str, Any]:
        # fetch dynamic params from sources; override
        return {}

    def merge_parameters(self, ctx: TaskContext, dynamic_params: Dict[str, Any]):
        # merge defaults + variant + incoming + dynamic
        from artemis.core.config import task_default, task_variant
        defaults = task_default(ctx.task_code)
        # strict policy: task_variant may raise; let it bubble to fail the phase
        variant_cfg = task_variant(ctx.task_code, ctx.incoming_params)
        ctx.params = {**defaults, **variant_cfg, **dynamic_params, **ctx.incoming_params}
        if ctx.logger:
            ctx.logger.info({'event': 'merge_parameters', 'params_keys': list(ctx.params.keys()), 'run_id': ctx.run_id})

    def before_execute(self, ctx: TaskContext):
        # optional hook
        pass

    def execute(self, ctx: TaskContext) -> Any:
        # main work; override
        return None

    def post_process(self, ctx: TaskContext, result: Any) -> Any:
        return result

    def sink(self, ctx: TaskContext, processed: Any):
        # write side effects; override
        pass

    def finalize(self, ctx: TaskContext):
        """Final hook after sink: safe place to set ctx.stats or emit final metrics."""
        pass

    def _run_phase(self, ctx: TaskContext, name: str, fn, *args, **kwargs):
        """Run a single phase with unified logging & timing.
        Returns (result, duration_ms). Exceptions propagate upward after logging.
        """
        start = time.time()
        if ctx.logger:
            ctx.logger.debug({'event': 'phase', 'phase': name, 'action': 'enter', 'run_id': ctx.run_id})
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            if ctx.logger:
                ctx.logger.error({'event': 'phase', 'phase': name, 'action': 'error', 'error': str(e), 'duration_ms': duration_ms, 'run_id': ctx.run_id})
            raise
        duration_ms = int((time.time() - start) * 1000)
        if ctx.logger:
            ctx.logger.info({'event': 'phase', 'phase': name, 'action': 'ok', 'duration_ms': duration_ms, 'run_id': ctx.run_id})
        return result, duration_ms

    def run(self, ctx: TaskContext):
        ctx.set_status(TaskStatus.RUNNING.value)
        if ctx.logger:
            ctx.logger.info({'event': 'task_start', 'task_code': ctx.task_code, 'run_id': ctx.run_id})
        phase_durations = {}
        failed_phase = None
        try:
            # parameter_check
            _, d = self._run_phase(ctx, 'parameter_check', self.parameter_check, ctx)
            phase_durations['parameter_check'] = d
            # load_dynamic_parameters
            dyn, d = self._run_phase(ctx, 'load_dynamic_parameters', self.load_dynamic_parameters, ctx)
            phase_durations['load_dynamic_parameters'] = d
            # load_task_config (merge)
            _, d = self._run_phase(ctx, 'load_task_config', self.merge_parameters, ctx, dyn)
            phase_durations['load_task_config'] = d
            # before_execute
            _, d = self._run_phase(ctx, 'before_execute', self.before_execute, ctx)
            phase_durations['before_execute'] = d
            # execute
            res, d = self._run_phase(ctx, 'execute', self.execute, ctx)
            phase_durations['execute'] = d
            # post_process
            processed, d = self._run_phase(ctx, 'post_process', self.post_process, ctx, res)
            phase_durations['post_process'] = d
            # sink
            _, d = self._run_phase(ctx, 'sink', self.sink, ctx, processed)
            phase_durations['sink'] = d
            # finalize (no result expected)
            _, d = self._run_phase(ctx, 'finalize', self.finalize, ctx)
            phase_durations['finalize'] = d

            ctx.set_status(TaskStatus.SUCCESS.value)
            # persist durations into stats for external API consumers
            ctx.stats['phase_durations_ms'] = phase_durations
            ctx.stats['total_duration_ms'] = sum(phase_durations.values())
            if ctx.logger:
                ctx.logger.info({
                    'event': 'task_success',
                    'task_code': ctx.task_code,
                    'run_id': ctx.run_id,
                    'durations_ms': phase_durations,
                    'total_ms': ctx.stats['total_duration_ms']
                })
        except Exception as e:
            failed_phase = failed_phase or ctx.status or 'unknown'
            ctx.set_status(TaskStatus.FAILED.value)
            ctx.set_error(str(e))
            # capture partial durations
            ctx.stats['phase_durations_ms'] = phase_durations
            if ctx.logger:
                ctx.logger.error({
                    'event': 'task_failed',
                    'task_code': ctx.task_code,
                    'error': str(e),
                    'run_id': ctx.run_id,
                    'failed_phase': failed_phase,
                    'durations_ms': phase_durations
                })
            raise
        finally:
            ctx.close()

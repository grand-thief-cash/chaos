from typing import Any, Dict, List, Optional

from artemis.consts import TaskStatus, DeptServices
from artemis.core import TaskContext
from artemis.core.task_registry import registry
from .base import BaseTaskUnit


class ParentTaskUnit(BaseTaskUnit):
    def fan_out(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """Return a list of child specs.

        Each spec should be:
          {"key": <child_task_code:str>, "params": <dict|None>}
        """
        return []

    def sink(self, ctx: TaskContext, processed: Any):
        """Parent task doesn't sink by default; children do."""
        return

    def _report_progress(self, ctx: TaskContext, message: Optional[str] = None):
        total = int(getattr(ctx, "children_total", 0) or 0)
        if total <= 0:
            return

        current = int(getattr(ctx, "children_completed", 0) or 0)

        cronjob_cli = None
        try:
            cronjob_cli = (getattr(ctx, 'dept_http', {}) or {}).get(DeptServices.CRONJOB)
        except Exception:
            cronjob_cli = None

        # preferred new design: delegate to cronjob client
        if cronjob_cli and hasattr(cronjob_cli, 'progress'):
            try:
                cronjob_cli.progress(ctx, current=current, total=total, message=message or f"children {current}/{total} done")
                return
            except Exception:
                pass

        # legacy fallback
        if not cronjob_cli:
            return
        try:
            cronjob_cli.progress(current, total, message=message or f"children {current}/{total} done")
        except Exception:
            # 进度上报失败不影响主流程
            if ctx.logger:
                ctx.logger.warning({
                    'event': 'parent_progress_failed',
                    'current': current,
                    'total': total,
                    'run_id': ctx.run_id,
                })

    def _build_child_ctx(self, parent_ctx: TaskContext, child_task_code: str, child_params: Dict[str, Any]) -> TaskContext:
        """Create a child TaskContext without importing HTTP models.

        TaskContext currently requires TaskRunReq in __init__, so we create an
        uninitialized instance and fill the minimal fields that BaseTaskUnit uses.
        """
        child_ctx: TaskContext = object.__new__(TaskContext)  # type: ignore

        # --- minimal meta/params ---
        # task_meta must provide run_id/task_code/async_mode/exec_type/task_id/callback_endpoints
        # We reuse parent's meta to keep callback endpoints & execution flags consistent.
        child_ctx.task_meta = parent_ctx.task_meta
        child_ctx.incoming_params = child_params or {}
        child_ctx.params = {}

        # --- timings / status ---
        import time

        child_ctx.start_ts = time.time()
        child_ctx.end_ts = None
        child_ctx.status = TaskStatus.PENDING.value
        child_ctx.error = None

        # --- child counters/stats ---
        child_ctx.children_total = 0
        child_ctx.children_completed = 0
        child_ctx.stats = {}

        # --- inherit logger & callback from parent ---
        child_ctx.logger = parent_ctx.logger
        child_ctx.callback = getattr(parent_ctx, "callback", None)

        # resolve exec class
        child_ctx.exec_cls = registry.get_task(child_task_code)
        if not child_ctx.exec_cls:
            raise ValueError(f"child task '{child_task_code}' not registered")

        return child_ctx

    def _validate_child_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(spec, dict):
            raise ValueError(f"child spec must be dict, got: {type(spec)}")
        key = spec.get('key')
        if not key or not isinstance(key, str):
            raise ValueError(f"child spec requires 'key' as str, got: {key!r}")
        params = spec.get('params') or {}
        if not isinstance(params, dict):
            raise ValueError(f"child spec 'params' must be dict, got: {type(params)}")
        return {'key': key, 'params': params}

    def run(self, ctx: TaskContext):
        """Run parent prework via BaseTaskUnit lifecycle, then fan-out children.

        保持原设计：parent 负责计算 child specs；child 负责具体执行。
        同时对齐 BaseTaskUnit 的统计字段（phase durations / total duration）以及 callback/logger 继承。
        """
        ctx.set_status(TaskStatus.RUNNING.value)
        if ctx.logger:
            ctx.logger.info({'event': 'task_start', 'task_code': ctx.task_code, 'run_id': ctx.run_id})

        phase_durations: Dict[str, int] = {}
        try:
            # parent phases (same as BaseTaskUnit, but parent sink is no-op)
            _, d = self._run_phase(ctx, 'parameter_check', self.parameter_check, ctx)
            phase_durations['parameter_check'] = d
            dyn, d = self._run_phase(ctx, 'load_dynamic_parameters', self.load_dynamic_parameters, ctx)
            phase_durations['load_dynamic_parameters'] = d
            _, d = self._run_phase(ctx, 'load_task_config', self.merge_parameters, ctx, dyn)
            phase_durations['load_task_config'] = d
            _, d = self._run_phase(ctx, 'before_execute', self.before_execute, ctx)
            phase_durations['before_execute'] = d
            res, d = self._run_phase(ctx, 'execute', self.execute, ctx)
            phase_durations['execute'] = d
            processed, d = self._run_phase(ctx, 'post_process', self.post_process, ctx, res)
            phase_durations['post_process'] = d
            # parent sink is intentionally skipped (no-op) to preserve design

            # fan-out children
            specs = self.fan_out(ctx) or []
            if not isinstance(specs, list):
                raise ValueError(f"fan_out must return List[dict], got: {type(specs)}")

            validated_specs = [self._validate_child_spec(s) for s in specs]
            ctx.mark_child_total(len(validated_specs))
            # initial progress 0/total
            self._report_progress(ctx, message=f"children 0/{ctx.children_total} start")

            for idx, spec in enumerate(validated_specs):
                child_key = spec['key']
                child_params = dict(spec.get('params') or {})
                # keep parent_run_id inside params; avoid importing HTTP models
                child_params.setdefault('_meta', {})
                if isinstance(child_params.get('_meta'), dict):
                    child_params['_meta'].setdefault('parent_run_id', ctx.run_id)

                if ctx.logger:
                    ctx.logger.info({
                        'event': 'child_start',
                        'child_index': idx,
                        'child_key': child_key,
                        'run_id': ctx.run_id,
                    })
                try:
                    child_ctx = self._build_child_ctx(ctx, child_key, child_params)
                    child = child_ctx.exec_cls()
                    child.run(child_ctx)

                    ctx.inc_child_completed()
                    self._report_progress(ctx)

                    if ctx.logger:
                        ctx.logger.info({
                            'event': 'child_success',
                            'child_index': idx,
                            'child_key': child_key,
                            'run_id': ctx.run_id,
                        })
                except Exception as ce:
                    if ctx.logger:
                        ctx.logger.error({
                            'event': 'child_failure',
                            'child_index': idx,
                            'child_key': child_key,
                            'error': str(ce),
                            'run_id': ctx.run_id,
                        })
                    raise

            # finalize hook for parent
            _, d = self._run_phase(ctx, 'finalize', self.finalize, ctx)
            phase_durations['finalize'] = d

            # stats summary
            ctx.stats['children_total'] = ctx.children_total
            ctx.stats['children_completed'] = ctx.children_completed
            ctx.stats['phase_durations_ms'] = phase_durations
            ctx.stats['total_duration_ms'] = sum(phase_durations.values())

            ctx.set_status(TaskStatus.SUCCESS.value)
            if ctx.logger:
                ctx.logger.info({'event': 'task_success', 'task_code': ctx.task_code, 'run_id': ctx.run_id})
        except Exception as e:
            ctx.set_status(TaskStatus.FAILED.value)
            ctx.set_error(str(e))
            ctx.stats['children_total'] = ctx.children_total
            ctx.stats['children_completed'] = ctx.children_completed
            ctx.stats['phase_durations_ms'] = phase_durations
            if ctx.logger:
                ctx.logger.error({'event': 'task_failed', 'task_code': ctx.task_code, 'error': str(e), 'run_id': ctx.run_id})
            raise
        finally:
            ctx.close()

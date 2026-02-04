from typing import Any, Dict, List, Optional

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.task_registry import registry
from .base import BaseTaskUnit


class OrchestratorTaskUnit(BaseTaskUnit):
    def plan(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """Return a list of child specs.
        Each spec should be: {"key": <child_task_code:str>, "params": <dict|None>}
        """
        raise NotImplementedError

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

        if cronjob_cli and hasattr(cronjob_cli, 'progress'):
            try:
                cronjob_cli.progress(ctx, current=current, total=total, message=message or f"children {current}/{total} done")
                return
            except Exception:
                pass

        if not cronjob_cli:
            return
        try:
            cronjob_cli.progress(current, total, message=message or f"children {current}/{total} done")
        except Exception:
            if ctx.logger:
                ctx.logger.warning({
                    'event': 'parent_progress_failed',
                    'current': current,
                    'total': total,
                    'run_id': ctx.run_id,
                })

    def _build_child_ctx(self, parent_ctx: TaskContext, child_task_code: str, child_params: Dict[str, Any]) -> TaskContext:
        child_ctx: TaskContext = object.__new__(TaskContext)  # type: ignore

        child_ctx.task_meta = parent_ctx.task_meta
        child_ctx.incoming_params = child_params or {}
        child_ctx.params = {}

        import time
        child_ctx.start_ts = time.time()
        child_ctx.end_ts = None
        # Inherit run_id so logs can be traced together easily, or keep distinct?
        # Usually child reuses parent run_id for grouping in logs, OR we append suffix.
        # But here we rely on task_meta which shares run_id.

        child_ctx.status = "PENDING"
        child_ctx.error = None
        child_ctx.children_total = 0
        child_ctx.children_completed = 0
        child_ctx.stats = {}

        child_ctx.logger = parent_ctx.logger
        child_ctx.callback = getattr(parent_ctx, "callback", None)
        child_ctx.dept_http = getattr(parent_ctx, "dept_http", {}) # Pass clients down

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

    def _execute_strategy(self, ctx: TaskContext, phase_durations: Dict[str, int]) -> None:
        """Orchestrator strategy: plan -> loop children -> report progress."""

        # 1. Plan
        specs, d = self._run_phase(ctx, 'plan', self.plan, ctx)
        phase_durations['plan'] = d

        specs = specs or []
        if not isinstance(specs, list):
            raise ValueError(f"plan must return List[dict], got: {type(specs)}")

        validated_specs = [self._validate_child_spec(s) for s in specs]
        ctx.mark_child_total(len(validated_specs))

        # Initial progress
        self._report_progress(ctx, message=f"children 0/{ctx.children_total} start")

        # 2. Execute Children
        import time
        loop_start = time.time()

        for idx, spec in enumerate(validated_specs):
            child_key = spec['key']
            child_params = dict(spec.get('params') or {})

            # Metadata propagation
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

                # Run the child
                # Note: child.run() handles its own try/catch/stats/logging via BaseTaskUnit
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
                # If a child fails, we log it but usually continue (or fail fast?)
                # Current design: fail parent if any child raises unhandled exception.
                # But BaseTaskUnit.run catches exceptions, so child.run() shouldn't raise unless severe error.
                # However, if child.run() swallows error, we check status.
                if child_ctx.status != "SUCCESS":
                     if ctx.logger:
                        ctx.logger.error({
                            'event': 'child_failure',
                            'child_index': idx,
                            'child_key': child_key,
                            'error': child_ctx.error,
                            'run_id': ctx.run_id,
                        })
                     # Policy: Fail parent if child failed? Or partial success?
                     # Let's re-raise to fail parent for now to correspond to legacy behavior (conceptually)
                     raise RuntimeError(f"Child task {child_key} failed: {child_ctx.error}")

        phase_durations['execution_loop'] = int((time.time() - loop_start) * 1000)

        # 3. Post-loop stats
        ctx.stats['children_total'] = ctx.children_total
        ctx.stats['children_completed'] = ctx.children_completed

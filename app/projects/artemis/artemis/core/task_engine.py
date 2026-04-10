import threading
from typing import Any, Dict, Optional

from artemis.consts import TaskStatus, TaskMode, DeptServices
from artemis.core import TaskContext
from artemis.log import get_logger
from artemis.models import TaskRunReq


class TaskEngine:
    def __init__(self):
        self.logger = get_logger('TaskEngine')
        self._active_tasks: Dict[Any, threading.Event] = {}
        self._lock = threading.Lock()

    # ── cancel tracking ──────────────────────────────────────

    def _register_task(self, run_id) -> threading.Event:
        event = threading.Event()
        with self._lock:
            self._active_tasks[run_id] = event
        return event

    def _unregister_task(self, run_id):
        with self._lock:
            self._active_tasks.pop(run_id, None)

    def cancel_task(self, run_id) -> bool:
        """Signal cancellation for an active task. Returns True if found."""
        with self._lock:
            event = self._active_tasks.get(run_id)
        if event is not None:
            event.set()
            return True
        return False

    def is_canceled(self, run_id) -> bool:
        with self._lock:
            event = self._active_tasks.get(run_id)
        return event is not None and event.is_set()

    # ── execution ────────────────────────────────────────────

    @staticmethod
    def run_task(ctx):
        try:
            task = ctx.exec_cls()
            task.run(ctx)
            return ctx.status == TaskStatus.SUCCESS.value and not ctx.error
        except Exception as e:
            ctx.fail(e, phase=ctx.failed_phase or 'engine')
            if 'phase_durations_ms' not in ctx.stats:
                ctx.emit_failure_log(ctx.stats.get('phase_durations_ms'))
            # async + 顶层任务的失败场景下，触发 finalize_failed 回调
            cronjob_cli = None
            try:
                if getattr(ctx, 'async_mode', False):

                    try:
                        cronjob_cli = (getattr(ctx, 'dept_http', {}) or {}).get(DeptServices.CRONJOB)
                    except Exception:
                        cronjob_cli = None

                    # prefer new design: delegate to dept client
                    if cronjob_cli and hasattr(cronjob_cli, 'finalized') and not cronjob_cli.finalized(ctx):
                        cronjob_cli.finalize_failed(ctx, ctx.error)
                    # fallback legacy
                    elif getattr(ctx, 'callback', None) and not ctx.callback.finalized():
                        ctx.callback.finalize_failed(ctx.error)
            except Exception as fe:
                if ctx.logger:
                    ctx.logger.warning({'event':'callback_finalize_failed_error','error':str(fe),'task_code':ctx.task_code,'run_id': ctx.run_id})
            return False

    def _execute(self, ctx: TaskContext, async_mode: bool = False, cancel_event: Optional[threading.Event] = None):
        is_success = self.run_task(ctx)

        # If the task was externally canceled, skip finalize callback
        if cancel_event and cancel_event.is_set():
            ctx.set_status(TaskStatus.CANCELED.value)
            if ctx.logger:
                ctx.logger.info({'event': 'task_canceled_externally', 'task_code': ctx.task_code, 'run_id': ctx.run_id})
            return {
                'task_code': ctx.task_code,
                'duration_ms': ctx.duration_ms(),
                'stats': ctx.stats,
                'status': TaskStatus.CANCELED.value,
                'run_id': ctx.run_id,
                'task_id': ctx.task_id,
                'exec_type': ctx.exec_type,
                'error': ctx.error,
            }

        # async mode: send finalize callback once (if supported and not yet finalized)
        if async_mode:
            try:
                cronjob_cli = None
                try:
                    cronjob_cli = (getattr(ctx, 'dept_http', {}) or {}).get(DeptServices.CRONJOB)
                except Exception:
                    cronjob_cli = None

                if cronjob_cli and not cronjob_cli.finalized(ctx):
                    if is_success and ctx.status == TaskStatus.SUCCESS.value:
                        cronjob_cli.finalize_success(ctx, code=200, body='task completed successfully')
                    else:
                        cronjob_cli.finalize_failed(ctx, error_message=ctx.error)
                    if ctx.logger:
                        ctx.logger.info({'event': 'callback_finalized', 'task_code': ctx.task_code, 'run_id': ctx.run_id, 'result': is_success})
            except Exception as fe:
                if ctx.logger:
                    ctx.logger.warning({'event': 'callback_finalize_error', 'error': str(fe), 'task_code': ctx.task_code, 'run_id': ctx.run_id})

        # sync mode: return execution result to HTTP layer
        return {
            'task_code': ctx.task_code,
            'duration_ms': ctx.duration_ms(),
            'stats': ctx.stats,
            'status': ctx.status,
            'run_id': ctx.run_id,
            'task_id': ctx.task_id,
            'exec_type': ctx.exec_type,
            'error': ctx.error,
        }

    def run(self, task_run_req: TaskRunReq) -> dict:
        ctx = TaskContext(task_run_req)
        run_id = ctx.run_id
        cancel_event = self._register_task(run_id)

        def _execute_with_tracking(async_mode: bool):
            try:
                return self._execute(ctx, async_mode=async_mode, cancel_event=cancel_event)
            finally:
                self._unregister_task(run_id)

        if ctx.exec_type == TaskMode.SYNC.value:
            return _execute_with_tracking(async_mode=False)
        elif ctx.exec_type == TaskMode.ASYNC.value:
            threading.Thread(target=_execute_with_tracking, args=(True,), daemon=True).start()
            return {'task_code': ctx.task_meta.task_code,'accepted': True,'exec_type': ctx.task_meta.exec_type,'run_id': ctx.task_meta.run_id,'task_id': ctx.task_meta.task_id}
        return {}

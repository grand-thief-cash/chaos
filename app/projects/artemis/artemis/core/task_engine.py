import threading

from artemis.consts import TaskStatus, TaskMode
from artemis.core import TaskContext
from artemis.log import get_logger
from artemis.models import TaskRunReq


class TaskEngine:
    def __init__(self):
        self.logger = get_logger('TaskEngine')

    @staticmethod
    def run_task(ctx):
        try:
            task = ctx.exec_cls()
            task.run(ctx)
            return True
        except Exception as e:
            # 确保 ctx 已经标记失败并带有错误信息
            if ctx.status != TaskStatus.FAILED.value:
                try:
                    ctx.set_status(TaskStatus.FAILED.value)
                except Exception:
                    pass
            if not ctx.error:
                try:
                    ctx.set_error(str(e))
                except Exception:
                    pass
            if ctx.logger:
                ctx.logger.error({'event':'task_error','error':str(e),'task_code': ctx.task_code,'run_id': ctx.run_id})
            # async + 顶层任务的失败场景下，触发 finalize_failed 回调
            try:
                meta = ctx.task_meta
                # is_top_level = not meta.get('parent_run_id')
                cb = ctx.callback
                if ctx.async_mode and cb and not cb.finalized():
                    cb.finalize_failed(str(e))
            except Exception as fe:
                if ctx.logger:
                    ctx.logger.warning({'event':'callback_finalize_failed_error','error':str(fe),'task_code':ctx.task_code,'run_id': ctx.run_id})
            return False

    def _execute(self, ctx: TaskContext, async_mode: bool = False):
        is_success = self.run_task(ctx)

        # async mode: send finalize callback once (if supported and not yet finalized)
        if async_mode and getattr(ctx, 'callback', None) and not ctx.callback.finalized():
            try:
                if is_success and ctx.status == TaskStatus.SUCCESS.value:
                    ctx.callback.finalize_success(code=200, body='task completed successfully')
                else:
                    ctx.callback.finalize_failed(error_message=ctx.error or 'task completed failed')
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
        if ctx.exec_type == TaskMode.SYNC.value:
            return self._execute(ctx, async_mode=False)
        elif ctx.exec_type == TaskMode.ASYNC.value:
            threading.Thread(target=self._execute, args=(ctx, True), daemon=True).start()
            return {'task_code': ctx.task_meta.task_code,'accepted': True,'exec_type': ctx.task_meta.exec_type,'run_id': ctx.task_meta.run_id,'task_id': ctx.task_meta.task_id}
        return {}
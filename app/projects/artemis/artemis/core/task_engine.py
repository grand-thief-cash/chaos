
import threading

from artemis.callback.client import build_callback_client
from artemis.log.logger import get_logger
from . import task_registry
from .context import TaskContext
from .task_status import TaskStatus  # added for status checks


class TaskEngine:
    def __init__(self):
        self.logger = get_logger('TaskEngine')

    @staticmethod
    def run_unit(ctx, cls):
        try:
            unit = cls()
            unit.run(ctx)
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
                meta = ctx.incoming_params.get('meta')
                is_top_level = not meta.get('parent_run_id')
                cb = ctx.callback
                if ctx.async_mode and is_top_level and cb and not cb.finalized():
                    cb.finalize_failed(str(e))
            except Exception as fe:
                if ctx.logger:
                    ctx.logger.warning({'event':'callback_finalize_failed_error','error':str(fe),'task_code':ctx.task_code,'run_id': ctx.run_id})
            return False


    def _execute(self, ctx: TaskContext, async_mode: bool = False):
            cls = task_registry.get(ctx.task_code)
            if not cls:
                # 理论上在 HTTP 入口处已经做过校验，这里是兜底防御
                self.logger.error({'event': 'task_not_found', 'task_code': ctx.task_code})
                if async_mode:
                    return None
                raise ValueError(f"task '{ctx.task_code}' not found")
            base_logger = get_logger(ctx.task_code)
            ctx.set_logger(base_logger)
            try:
                ctx.callback = build_callback_client(ctx.incoming_params, logger=ctx.logger)
            except Exception as e:
                if ctx.logger:
                    ctx.logger.warning({'event':'callback_client_init_failed','error':str(e),'task_code':ctx.task_code,'run_id': ctx.run_id})

            success = self.run_unit(ctx, cls)

            # 仅在 async 模式且为顶层任务时，发送最终成功回调
            meta = ctx.incoming_params.get('meta')
            is_top_level = not meta.get('parent_run_id')
            if async_mode and is_top_level and ctx.callback and not ctx.callback.finalized():
                try:
                    if success and ctx.status == TaskStatus.SUCCESS.value:
                        ctx.callback.finalize_success(code=200, body='task completed successfully')
                        if ctx.logger:
                            ctx.logger.info({'event':'callback_finalize_success','task_code': ctx.task_code,'run_id': ctx.run_id})
                    # 失败的情况已经在 run_unit 的 except 块里处理过了
                except Exception as fe:
                    if ctx.logger:
                        ctx.logger.warning({'event':'callback_finalize_success_error','error':str(fe),'task_code': ctx.task_code,'run_id': ctx.run_id})

            if async_mode:
                # async 模式下，HTTP 层已在 run_async 返回 "accepted"，这里不需要同步返回结果
                return None

            # sync 模式：直接返回执行结果，由 HTTP 层决定如何暴露给调用方
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

    def run(self, task_code: str, incoming_params: dict) -> dict:
        ctx = TaskContext(task_code, incoming_params)

        if ctx.exec_type == 'SYNC':
            return self._execute(ctx, async_mode=False)
        elif ctx.exec_type == 'ASYNC':
            threading.Thread(target=self._execute, args=(ctx, True), daemon=True).start()
            return {'task_code': task_code,'accepted': True,'exec_type': ctx.exec_type,'run_id': ctx.run_id,'task_id': ctx.task_id}
        return {}

    # def run_async(self, task_code: str, incoming_params: dict, headers: dict | None = None) -> dict:
    #     import threading
    #     threading.Thread(target=self._execute, args=(task_code, incoming_params, headers, True), daemon=True).start()
    #     meta = (incoming_params.get('_meta') or {})
    #     return {'task_code': task_code,'accepted': True,'exec_type': str(meta.get('exec_type','ASYNC')).upper(),'run_id': meta.get('run_id'),'task_id': meta.get('task_id')}

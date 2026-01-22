from fastapi import APIRouter, HTTPException, Request

# 确保task注册代码执行
import artemis.task_units  # noqa: F401 registers tasks
from artemis.core import registry
from artemis.core.task_engine import TaskEngine
from artemis.log.logger import get_logger
from artemis.models import TaskRunReq

router = APIRouter()
engine = TaskEngine()
logger = get_logger('http.routes')

@router.get('/tasks')
async def tasks():
    logger.info("/task list requested")
    return {'tasks': registry.list_tasks()}


@router.post('/tasks/run')
async def run_task(request: Request):
    """Run a task either synchronously or asynchronously.

    入参由 cronjob 构建：{"meta": {...}, "body": ...}
    我们在这里统一反序列化/校验/兼容 legacy，然后再交给 TaskEngine。
    """
    payload = await request.json()
    task_run_req = TaskRunReq.model_validate(payload)

    # 先检查任务是否存在
    task_code = task_run_req.task_meta.task_code
    if not registry.get_task(task_code):
        logger.warning({'event': 'task_not_found', 'task_code': task_code})
        raise HTTPException(status_code=404, detail=f"task '{task_code}' not found")

    # meta, body = validate_params(task_req)
    logger.info({'event': 'task_run_request', "task_code":task_code, "req": task_run_req.model_dump()})

    try:
        result = engine.run(task_run_req)
        logger.info({'event': 'task_run_res','task_code': task_code,'result': result})
        return result
    except ValueError as ve:
        logger.warning(
            {
                'event': 'task_run_not_found',
                'task_code': task_code,
                'error': str(ve),
            },
            extra={'task_code': task_code},
        )
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(
            {
                'event': 'task_run_failure',
                'task_code': task_code,
                'error': str(e),
            },
            extra={'task_code': task_code},
        )
        raise HTTPException(status_code=500, detail='internal error')

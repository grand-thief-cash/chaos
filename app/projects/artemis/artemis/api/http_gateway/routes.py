from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

# 确保task注册代码执行
import artemis.task_units  # noqa: F401 registers tasks
from artemis.consts import TaskCode
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
    raw = registry.list_tasks()
    tasks = []
    for code, cls in raw.items():
        code_val = getattr(code, 'value', str(code))
        tasks.append({
            'task_code': code_val,
            'impl': getattr(cls, '__name__', str(cls)),
            'module': getattr(cls, '__module__', ''),
        })
    return {'tasks': tasks}


@router.post('/tasks/run/{task_code}')
async def run_task(task_code: TaskCode, request: Request):
    """Run a task either synchronously or asynchronously.
    入参由 cronjob 构建：{"meta": {...}, "body": ...}
    """
    payload = await request.json()
    try:
        task_run_req = TaskRunReq.model_validate(payload)
    except ValidationError as e:
        logger.warning({'event': 'invalid_task_req','errors': e.errors(),'input': payload})
        raise HTTPException(status_code=422, detail="Request validation failed")

    # 先检查任务是否存在
    if not registry.get_task(task_code):
        logger.warning({'event': 'task_not_found', 'task_code': task_code})
        raise HTTPException(status_code=404, detail=f"task '{task_code}' not found")
    task_run_req.task_meta.task_code = task_code
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

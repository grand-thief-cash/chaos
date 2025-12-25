from fastapi import APIRouter, HTTPException, Request

from artemis.core.task_engine import TaskEngine
from artemis.core.task_registry import list_tasks, get as get_task  # import get for existence check
from artemis.log.logger import get_logger
from artemis.models.task_meta import TaskMeta

router = APIRouter()
engine = TaskEngine()
logger = get_logger('http.routes')


def validate_params(payload) -> tuple[TaskMeta | dict, dict]:
    """反序列化 + 校验。

    约定：
      - meta 必填，且 run_id/task_id/exec_type 必填，callback_endpoints 可选
      - body 可选
      - meta 与 body 解耦
    返回 (meta_dict, body)
    """

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail='request_body_must_be_json_object')

    meta = payload.get('meta') if 'meta' in payload else {}
    body = payload.get('body') if 'body' in payload else {}
    exec_type = meta.get("exec_type")
    if exec_type is None or exec_type not in ['SYNC', 'ASYNC']:
        raise HTTPException(status_code=422, detail='exec_type in meta required')
    if 'task_id' not in meta:
        raise HTTPException(status_code=422, detail='task_id in meta required')
    if 'run_id' not in meta:
        raise HTTPException(status_code=422, detail='run_id in meta required')

    return meta, body


@router.get('/tasks')
async def tasks():
    logger.info("/task list requested")
    return {'tasks': list_tasks()}


@router.post('/tasks/{task_code}/run')
async def run_task(task_code: str, request: Request):
    """Run a task either synchronously or asynchronously.

    入参由 cronjob 构建：{"meta": {...}, "body": ...}
    我们在这里统一反序列化/校验/兼容 legacy，然后再交给 TaskEngine。
    """
    # 先检查任务是否存在
    if not get_task(task_code):
        logger.warning({'event': 'task_not_found', 'task_code': task_code})
        raise HTTPException(status_code=404, detail=f"task '{task_code}' not found")

    payload = await request.json()
    meta, body = validate_params(payload)
    logger.info(
        {
            'event': 'task_run_request',
            'task_code': task_code,
            'meta': meta,
            'body': body,
        }
    )

    try:
        result = engine.run(task_code, payload)
        logger.info(
            {
                'event': 'task_run_dispatched',
                'task_code': task_code,
                'exec_type': meta.exec_type,
                'result': result,
            },
        )
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

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from artemis.core.task_engine import TaskEngine
from artemis.core.task_registry import list_tasks
from artemis.log.logger import get_logger

router = APIRouter()
engine = TaskEngine()
logger = get_logger('http.routes')

class RunEnvelope(BaseModel):
    meta: dict
    body: dict | str | None = None

@router.get('/tasks')
async def tasks():
    logger.info("/task list requested")
    return {'tasks': list_tasks()}

@router.post('/tasks/{task_code}/run')
async def run_task(task_code: str, envelope: RunEnvelope, request: Request):
    meta = envelope.meta or {}
    body = envelope.body
    params = body if isinstance(body, dict) else {}
    exec_type = str(meta.get('exec_type','SYNC')).upper()
    logger.info({'event': 'task_run_request', 'task_code': task_code, 'meta_keys': list(meta.keys()), 'exec_type': exec_type}, extra={'task_code': task_code})
    try:
        headers_dict = dict(request.headers)
        combined = params.copy()
        combined['_meta'] = meta
        if exec_type == 'ASYNC':
            result = engine.run_async(task_code, combined, headers=headers_dict)
        else:
            result = engine.run(task_code, combined, headers=headers_dict)
        logger.info({'event': 'task_run_dispatched', 'task_code': task_code, 'exec_type': exec_type}, extra={'task_code': task_code})
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and ctx.is_valid and exec_type != 'ASYNC':
                from fastapi.responses import JSONResponse
                resp = JSONResponse(result)
                resp.headers['X-Trace-Id'] = f"{ctx.trace_id:032x}"
                return resp
        except Exception:
            pass
        return result
    except ValueError as ve:
        logger.warning({'event': 'task_run_not_found', 'task_code': task_code, 'error': str(ve)}, extra={'task_code': task_code})
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error({'event': 'task_run_failure', 'task_code': task_code, 'error': str(e)}, extra={'task_code': task_code})
        raise HTTPException(status_code=500, detail='internal error')

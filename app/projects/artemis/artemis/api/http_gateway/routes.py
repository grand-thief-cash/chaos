from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

# 确保task注册代码执行
import artemis.task_units  # noqa: F401 registers tasks
from artemis.core import registry, cfg_mgr
from artemis.core.runtime_files import RuntimeFileService
from artemis.core.task_engine import TaskEngine
from artemis.log.logger import get_logger
from artemis.models import (
    TaskRunReq,
    TaskYamlGetResp,
    TaskYamlPutReq,
    TaskUnitsTreeResp,
    TaskUnitFileGetResp,
    TaskUnitFilePutReq,
    TaskUnitFileCreateReq,
    TaskUnitRegisterReq,
    TaskUnitRegisterResp,
)

router = APIRouter()
engine = TaskEngine()
logger = get_logger('http.routes')
file_service = RuntimeFileService()

@router.get('/tasks')
async def tasks():
    logger.info("/task list requested")
    raw = registry.list_tasks()
    tasks = []
    for code, spec in raw.items():
        code_val = getattr(code, 'value', str(code))
        tasks.append({
            'task_code': code_val,
            'impl': getattr(spec, 'class_name', ''),
            'module': getattr(spec, 'module', ''),
        })
    return {'tasks': tasks}


@router.post('/tasks/run/{task_code}')
async def run_task(task_code: str, request: Request):
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
    if not registry.has_task(task_code):
        logger.warning({'event': 'task_not_found', 'task_code': task_code})
        raise HTTPException(status_code=404, detail=f"task '{task_code}' not found")
    task_run_req.task_meta.task_code = task_code  # type: ignore[assignment]
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


@router.get('/runtime/task-yaml', response_model=TaskYamlGetResp)
async def get_task_yaml():
    try:
        info = cfg_mgr.read_task_yaml_content()
        return TaskYamlGetResp(**info)
    except Exception as e:
        logger.error({'event': 'task_yaml_read_failed', 'error': str(e)})
        raise HTTPException(status_code=500, detail='failed to read task.yaml')


@router.put('/runtime/task-yaml', response_model=TaskYamlGetResp)
async def update_task_yaml(req: TaskYamlPutReq):
    try:
        info = cfg_mgr.write_task_yaml_content(req.content)
        return TaskYamlGetResp(**info)
    except Exception as e:
        logger.error({'event': 'task_yaml_write_failed', 'error': str(e)})
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/runtime/task-units/tree', response_model=TaskUnitsTreeResp)
async def task_units_tree():
    items = file_service.build_task_units_tree()
    return TaskUnitsTreeResp(root=str(file_service.task_units_root()), items=items)


@router.get('/runtime/task-units/file', response_model=TaskUnitFileGetResp)
async def task_units_file(path: str):
    try:
        content = file_service.read_task_unit(path)
        return TaskUnitFileGetResp(path=path, content=content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='file not found')
    except Exception as e:
        logger.error({'event': 'task_unit_read_failed', 'path': path, 'error': str(e)})
        raise HTTPException(status_code=400, detail=str(e))


@router.put('/runtime/task-units/file', response_model=TaskUnitFileGetResp)
async def update_task_units_file(req: TaskUnitFilePutReq):
    try:
        file_service.write_task_unit(req.path, req.content, create=False)
        return TaskUnitFileGetResp(path=req.path, content=req.content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='file not found')
    except Exception as e:
        logger.error({'event': 'task_unit_write_failed', 'path': req.path, 'error': str(e)})
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/runtime/task-units/file', response_model=TaskUnitFileGetResp)
async def create_task_units_file(req: TaskUnitFileCreateReq):
    try:
        file_service.write_task_unit(req.path, req.content, create=True)
        return TaskUnitFileGetResp(path=req.path, content=req.content)
    except FileExistsError:
        raise HTTPException(status_code=409, detail='file already exists')
    except Exception as e:
        logger.error({'event': 'task_unit_create_failed', 'path': req.path, 'error': str(e)})
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/runtime/task-units/register', response_model=TaskUnitRegisterResp)
async def register_task_unit(req: TaskUnitRegisterReq):
    try:
        registry.register(req.task_code, module=req.module, class_name=req.class_name)
        return TaskUnitRegisterResp(task_code=req.task_code, module=req.module, class_name=req.class_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({'event': 'task_unit_register_failed', 'task_code': req.task_code, 'error': str(e)})
        raise HTTPException(status_code=500, detail='failed to register task')

import yaml
from fastapi import APIRouter, HTTPException, Request, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

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
from artemis.telemetry.middleware import add_trace_id_middleware
from artemis.telemetry.otel import instrument_fastapi_app, init_otel

app = FastAPI(title='Artemis Gateway')
router = APIRouter()

# 初始化 OTEL（如果配置启用），并对 FastAPI App 做自动 instrumentation
init_otel()
instrument_fastapi_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 X-Trace-Id middleware，确保所有请求都带有可追踪的 trace_id
add_trace_id_middleware(app)

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
            'is_dynamic': getattr(spec, 'is_dynamic', False),
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
        raise HTTPException(status_code=422, detail=f"Request validation failed: {e.errors()}")
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
        yaml.safe_load(req.content)  # validate
        info = cfg_mgr.write_task_yaml_content(req.content)
        return TaskYamlGetResp(**info)
    except yaml.YAMLError as ye:
        raise HTTPException(status_code=422, detail=f"Invalid YAML format: {str(ye)}")
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
        registry.register(
            req.task_code,
            module=req.module,
            class_name=req.class_name,
            is_dynamic=True  # Mark as dynamic
        )
        return TaskUnitRegisterResp(task_code=req.task_code, module=req.module, class_name=req.class_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({'event': 'task_unit_register_failed', 'task_code': req.task_code, 'error': str(e)})
        raise HTTPException(status_code=500, detail='failed to register task')

@router.get('/tasks/unregistered')
async def list_unregistered_tasks():
    try:
        tasks = registry.scan_unregistered()
        return {'tasks': tasks}
    except Exception as e:
        logger.error({'event': 'scan_unregistered_failed', 'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/tasks/unregister/{task_code}')
async def unregister_task(task_code: str):
    try:
        registry.unregister(task_code)
        logger.info({'event': 'task_unregistered', 'task_code': task_code})
        return {'status': 'ok'}
    except ValueError as e:
         raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({'event': 'task_unregister_failed', 'task_code': task_code, 'error': str(e)})
        raise HTTPException(status_code=500, detail='internal error')

@router.post('/runtime/task-units/rename')
async def rename_task_unit_file(req: dict):
    old_path = req.get('old_path')
    new_path = req.get('new_path')
    if not old_path or not new_path:
        raise HTTPException(status_code=400, detail="old_path and new_path are required")
    try:
        file_service.rename_task_unit(old_path, new_path)
        return {'status': 'ok'}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Destination file already exists")
    except Exception as e:
        logger.error({'event': 'task_unit_rename_failed', 'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@router.delete('/runtime/task-units/file')
async def delete_task_unit_file(path: str):
    try:
        # 1. Identify tasks in this file
        # We can reuse similar logic to scan_unregistered but targeted
        import importlib
        import inspect
        from artemis.task_units.base import BaseTaskUnit
        
        # Calculate module name from path
        # Assuming path is relative to task_units e.g. zh/stock.py
        rel_path = path.replace('\\', '/').split('.')[0].replace('/', '.')
        # But we need full module path: artemis.task_units.zh.stock
        module_name = f"artemis.task_units.{rel_path}"
        
        # 2. Check for registered tasks
        tasks_to_unregister = []
        try:
            module = importlib.import_module(module_name)
            # Find all task classes defined in this module
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseTaskUnit) and 
                    obj is not BaseTaskUnit and 
                    obj.__module__ == module.__name__
                ):
                    # Check if registered
                    for task_code, spec in registry.list_tasks().items():
                        if spec.module == module_name and spec.class_name == name:
                            if not spec.is_dynamic:
                                raise ValueError(f"Cannot delete file containing static task: {task_code}")
                            tasks_to_unregister.append(task_code)
                            
        except ImportError:
            # If module cannot be imported, maybe it's broken or just a file
            pass
        except ValueError as ve:
             raise HTTPException(status_code=400, detail=str(ve))

        # 3. Unregister dynamic tasks
        for code in tasks_to_unregister:
            registry.unregister(code)
            logger.info(f"Auto-unregistered task {code} prior to deletion")

        # 4. Delete file
        file_service.delete_task_unit(path)
        return {'status': 'ok'}
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error({'event': 'task_unit_delete_failed', 'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)

# app/infra/pyinfra/components/fastapi_server/factory.py
from typing import Dict
from components.fastapi_server.component import FastAPIServerComponent
from components.fastapi_server.schema import FastAPIServerConfig
from core.container import Container

def create_and_register_fastapi_server(config: Dict, app_name: str) -> FastAPIServerComponent:
    """创建并注册 FastAPI 服务器组件"""
    server_config = FastAPIServerConfig(**config.get("fastapi_server", {}), app_name=app_name)
    component = FastAPIServerComponent(server_config)

    # 注册到容器和生命周期
    Container.register("fastapi_server", component)
    from core.lifecycle import LifecycleManager
    LifecycleManager.register_component(component)

    return component
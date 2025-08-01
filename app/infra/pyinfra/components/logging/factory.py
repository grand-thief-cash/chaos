# components/logging/factory.py
from typing import Dict
from config.schema import LoggingConfig
from .component import LoggingComponent
from core.container import Container

def create_and_register_logging(config: Dict, app_name: str) -> LoggingComponent:
    """创建并注册日志组件"""
    logging_config = LoggingConfig(**config.get("logging", {}), app_name=app_name)
    component = LoggingComponent(logging_config)

    # 注册到容器和生命周期
    Container.register("logging", component)
    from core.lifecycle import LifecycleManager
    LifecycleManager.register_component(component)

    return component
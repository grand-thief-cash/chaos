# components/logging/__init__.py
from .factory import create_and_register_logging

def setup_logging(config: dict, app_name: str):
    """模块入口：初始化并注册日志系统"""
    return create_and_register_logging(config, app_name)
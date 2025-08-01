# pyinfra/hooks/before_start.py
from ..core.container import Container
from . import register_hook
import logging

logger = logging.getLogger(__name__)

@register_hook('before_start')
def initialize_essential_services():
    """在应用启动前初始化必要服务"""
    logger.info("Initializing essential services before start")
    # 示例：可以在这里初始化配置日志
    if not Container.resolve("logging"):
        logging.basicConfig(level=logging.INFO)
        logging.warning("Logging system not initialized, using basic config")

@register_hook('before_start')
def validate_components():
    """验证所有已注册组件"""
    registered = Container.list_registered()
    logger.info(f"Validating {len(registered)} registered components")
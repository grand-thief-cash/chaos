# pyinfra/hooks/before_shutdown.py
from hooks import register_hook
import logging

logger = logging.getLogger(__name__)

@register_hook('before_shutdown')
def deregister_service():
    """从服务发现取消注册"""
    logger.info("Deregistering from service discovery")

@register_hook('before_shutdown')
def close_external_connections():
    """关闭所有外部连接"""
    logger.info("Closing all external connections")
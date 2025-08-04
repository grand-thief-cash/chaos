# pyinfra/hooks/after_shutdown.py
from hooks import register_hook
import logging

logger = logging.getLogger(__name__)

@register_hook('after_shutdown')
def cleanup_resources():
    """清理残留资源"""
    logger.info("Cleaning up residual resources")

@register_hook('after_shutdown')
def notify_shutdown_complete():
    """关闭完成通知"""
    logger.info("Application shutdown completed")
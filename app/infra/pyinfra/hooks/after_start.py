# pyinfra/hooks/after_start.py
from hooks import register_hook
import logging

logger = logging.getLogger(__name__)

@register_hook('after_start')
def notify_service_ready():
    """应用启动完成后通知"""
    logger.info("Application startup completed, service is ready")

@register_hook('after_start')
def start_health_checks():
    """启动健康检查"""
    logger.info("Starting background health checks")
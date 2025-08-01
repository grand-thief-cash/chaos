
from opentelemetry import trace

from python.container import container
from python.logger.init import get_logger
from python.logger.settings import settings


def setup_infrastructure():
    """基础设施初始化"""
    # 注册核心组件
    container.register_factory("log", init_logging)

    # 其他组件注册...
    # container.register_factory("database", init_db)
    # container.register_factory("http_client", init_http_client)

def main():
    """使用容器生命周期管理的主入口"""
    with container.lifecycle():
        logger = get_logger(__name__)
        logger.info("Application started", extra={"config": settings.dict()})

        try:
            with trace.get_tracer(__name__).start_as_current_span("main_operation"):
                logger.debug("Processing data...")
                # 业务逻辑...
                logger.info("Operation completed")
        except Exception as e:
            logger.error("Unexpected error", exc_info=True)

if __name__ == "__main__":
    setup_infrastructure()
    main()
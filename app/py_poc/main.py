# py_poc/main.py
import logging
from app import PyAPP
from controllers.data_controller import DataController
from core.container import Container


def main():
    app = PyAPP(
        config_path="config/app.yaml",
        app_name="data-fetcher"
    )

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # 初始化基础设施
        app.initialize()
        logger = logging.getLogger(__name__)

        # 设置业务逻辑
        setup_business_controllers()

        # 启动应用
        app.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
    finally:
        app.stop()


def setup_business_controllers():
    """设置业务控制器"""
    logger = logging.getLogger(__name__)

    # 获取 FastAPI 服务器实例
    fastapi_component = Container.resolve("fastapi_server")
    if fastapi_component:
        fastapi_app = fastapi_component.get_app()

        # 创建并注册控制器
        data_controller = DataController()
        fastapi_app.include_router(data_controller.get_router())

        logger.info("Business controllers registered to FastAPI server")
    else:
        logger.warning("FastAPI server component not found")

    # 检查GRPC客户端是否可用
    grpc_component = Container.resolve("grpc_clients")
    if grpc_component:
        logger.info(f"GRPC clients available: {list(grpc_component.clients.keys())}")
    else:
        logger.warning("GRPC clients component not found")


if __name__ == "__main__":
    main()
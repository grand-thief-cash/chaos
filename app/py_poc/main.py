# app/data-fetcher/main.py
import logging
from fastapi import APIRouter
from core.container import Container
from app import PyAPP


def main():
    # 创建应用实例
    app = PyAPP(
        config_path="config/app.yaml",
        app_name="data-fetcher"
    )

    # 先设置基础日志配置，防止后续错误时logger未定义
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # 初始化基础设施
        app.initialize()

        # 重新获取配置好的logger
        logger = logging.getLogger(__name__)

        # 添加你的业务逻辑
        setup_business_logic()

        # 启动应用（会启动所有组件并等待关闭信号）
        app.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
    finally:
        # 确保清理资源
        app.stop()


def setup_business_logic():
    """设置业务逻辑"""
    logger = logging.getLogger(__name__)
    # logger.info("Setting up business logic")

    # 获取 FastAPI 服务器实例
    fastapi_component = Container.resolve("fastapi_server")
    if fastapi_component:
        fastapi_app = fastapi_component.get_app()

        # 创建业务路由
        api_router = APIRouter(prefix="/api/v1")

        # 数据获取相关路由
        @api_router.get("/data/fetch")
        async def fetch_data():
            """获取数据接口"""
            logger.info("Fetching data requested")
            try:
                # 这里添加你的数据获取逻辑
                data = await perform_data_fetch()
                return {
                    "status": "success",
                    "data": data,
                    "message": "Data fetched successfully"
                }
            except Exception as e:
                logger.error(f"Data fetch failed: {str(e)}")
                return {
                    "status": "error",
                    "message": str(e)
                }

        @api_router.get("/data/status")
        async def get_fetch_status():
            """获取数据获取状态"""
            logger.info("Data fetch status requested")
            return {
                "status": "active",
                "last_fetch": "2024-01-01T00:00:00Z",
                "next_fetch": "2024-01-01T01:00:00Z"
            }

        @api_router.post("/data/refresh")
        async def refresh_data():
            """手动刷新数据"""
            logger.info("Manual data refresh requested")
            try:
                result = await trigger_data_refresh()
                return {
                    "status": "success",
                    "message": "Data refresh triggered",
                    "result": result
                }
            except Exception as e:
                logger.error(f"Data refresh failed: {str(e)}")
                return {
                    "status": "error",
                    "message": str(e)
                }

        # 注册路由到 FastAPI 应用
        fastapi_app.include_router(api_router)

        logger.info("Business logic routes registered to FastAPI server")
    else:
        logger.warning("FastAPI server component not found, skipping route registration")


async def perform_data_fetch():
    """执行数据获取逻辑"""
    logger = logging.getLogger(__name__)
    logger.info("Performing data fetch operation")

    # 模拟数据获取逻辑
    import asyncio
    await asyncio.sleep(1)  # 模拟异步操作

    return {
        "records": [
            {"id": 1, "name": "sample_data_1", "value": 100},
            {"id": 2, "name": "sample_data_2", "value": 200}
        ],
        "total": 2,
        "timestamp": "2024-01-01T00:00:00Z"
    }


async def trigger_data_refresh():
    """触发数据刷新"""
    logger = logging.getLogger(__name__)
    logger.info("Triggering data refresh")

    # 模拟刷新逻辑
    import asyncio
    await asyncio.sleep(0.5)

    return {
        "refresh_id": "refresh_123",
        "started_at": "2024-01-01T00:00:00Z"
    }


if __name__ == "__main__":
    main()
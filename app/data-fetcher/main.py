# my_app/main.py
import logging

from app import PyAPP

def main():
    # 创建应用实例
    app = PyAPP(
        config_path="config/app.yaml",
        app_name="data-fetcher"
    )
    try:
        # 初始化基础设施
        app.initialize()

        # 获取日志组件进行业务逻辑开发
        logger = logging.getLogger(__name__)
        logger.info("Application starting with pyinfra infrastructure")

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
    logger.info("Setting up business logic")

    # 这里添加你的业务初始化代码
    # 比如：启动 web 服务器、消息队列消费者等


if __name__ == "__main__":
    main()
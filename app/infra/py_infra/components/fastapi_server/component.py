# components/fastapi_server/component.py
import asyncio
import threading
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
from typing import Optional
from core.component import BaseComponent
from components.fastapi_server.schema import FastAPIServerConfig
from components.logging.context import set_trace_id, set_execution_time
import uuid

logger = logging.getLogger(__name__)


class FastAPIServerComponent(BaseComponent):
    def __init__(self, config: FastAPIServerConfig):
        super().__init__(config)
        self.config: FastAPIServerConfig = config
        self.app: Optional[FastAPI] = None
        self.server: Optional[uvicorn.Server] = None
        self.server_thread: Optional[threading.Thread] = None
        self._setup_app()

    def _setup_app(self):
        """初始化 FastAPI 应用"""
        self.app = FastAPI(
            title=self.config.title or self.config.app_name,
            description=self.config.description,
            version=self.config.version,
            docs_url=self.config.docs_url,
            redoc_url=self.config.redoc_url,
            openapi_url=self.config.openapi_url,
            debug=self.config.debug
        )

        # 添加 CORS 中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=self.config.cors_methods,
            allow_headers=self.config.cors_headers,
        )

        # 添加日志中间件
        self._setup_logging_middleware()

        # 添加基础路由
        self._setup_basic_routes()

    def _setup_logging_middleware(self):
        """设置日志中间件"""

        @self.app.middleware("http_server")
        async def logging_middleware(request: Request, call_next):
            # 生成追踪ID
            trace_id = str(uuid.uuid4())
            set_trace_id(trace_id)

            start_time = time.time()

            # 记录请求开始
            logger.info(f"Request started: {request.method} {request.url}")

            try:
                response = await call_next(request)

                # 计算执行时间
                execution_time = time.time() - start_time
                set_execution_time(execution_time)

                # 记录请求完成
                logger.info(
                    f"Request completed: {request.method} {request.url} "
                    f"Status: {response.status_code} Time: {execution_time:.3f}s"
                )

                # 添加追踪ID到响应头
                response.headers["X-Trace-ID"] = trace_id

                return response

            except Exception as e:
                execution_time = time.time() - start_time
                set_execution_time(execution_time)

                logger.error(
                    f"Request failed: {request.method} {request.url} "
                    f"Error: {str(e)} Time: {execution_time:.3f}s"
                )
                raise

    def _setup_basic_routes(self):
        """设置基础路由"""

        @self.app.get("/health")
        async def health_check():
            """健康检查端点"""
            return {
                "status": "healthy",
                "app_name": self.config.app_name,
                "version": self.config.version
            }

        @self.app.get("/")
        async def root():
            """根路径"""
            return {
                "message": f"Welcome to {self.config.app_name}",
                "version": self.config.version,
                "docs": self.config.docs_url
            }

    def get_app(self) -> FastAPI:
        """获取 FastAPI 应用实例"""
        return self.app

    def start(self):
        """启动 FastAPI 服务器"""
        if self.is_active:
            logger.warning("FastAPI server is already running")
            return

        logger.info(f"Starting FastAPI server on {self.config.host}:{self.config.port}")

        # 创建 uvicorn 配置
        uvicorn_config = uvicorn.Config(
            app=self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info" if self.config.debug else "warning",
            access_log=self.config.access_log,
            reload=self.config.reload,
            workers=1  # 在线程中运行时只能使用单个worker
        )

        self.server = uvicorn.Server(uvicorn_config)

        # 在新线程中启动服务器
        def run_server():
            asyncio.run(self.server.serve())

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # 等待服务器启动
        import time
        timeout = 10
        start_time = time.time()
        while not self.server.started and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if self.server.started:
            super().start()
            logger.info(f"FastAPI server started successfully on http_server://{self.config.host}:{self.config.port}")
        else:
            raise RuntimeError("Failed to start FastAPI server within timeout")

    def stop(self):
        """停止 FastAPI 服务器"""
        if not self.is_active:
            logger.warning("FastAPI server is not running")
            return

        logger.info("Stopping FastAPI server...")

        if self.server:
            self.server.should_exit = True

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)

        super().stop()
        logger.info("FastAPI server stopped")

    def health_check(self) -> bool:
        """健康检查"""
        return self.is_active and self.server and self.server.started
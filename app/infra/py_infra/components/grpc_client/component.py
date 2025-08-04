# infra/pyinfra/components/grpc_client/component.py
import grpc
import logging
import threading
import time
from typing import Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from core.component import BaseComponent
from components.grpc_client.schema import GRPCClientsConfig, GRPCClientConfig
from components.logging.context import get_trace_id

logger = logging.getLogger(__name__)


class GRPCClientComponent(BaseComponent):
    """GRPC客户端管理组件"""

    def __init__(self, config: GRPCClientsConfig):
        super().__init__(config)
        self.config: GRPCClientsConfig = config
        self.clients: Dict[str, grpc.Channel] = {}
        self.client_configs: Dict[str, GRPCClientConfig] = {}
        self.health_check_executor: Optional[ThreadPoolExecutor] = None
        self.health_check_stop_event = threading.Event()

    def start(self):
        """启动GRPC客户端"""
        logger.info("Starting GRPC clients...")

        # 创建所有客户端连接
        for name, client_config in self.config.clients.items():
            if client_config.enabled:
                self._create_client(name, client_config)

        # 启动健康检查
        if self.config.enable_health_check:
            self._start_health_check()

        super().start()
        logger.info(f"GRPC clients started, total: {len(self.clients)}")

    def stop(self):
        """停止GRPC客户端"""
        logger.info("Stopping GRPC clients...")

        # 停止健康检查
        if self.health_check_executor:
            self.health_check_stop_event.set()
            self.health_check_executor.shutdown(wait=True)

        # 关闭所有客户端连接
        for name, channel in self.clients.items():
            try:
                logger.info(f"Closing GRPC client: {name}")
                channel.close()
            except Exception as e:
                logger.error(f"Error closing GRPC client {name}: {str(e)}")

        self.clients.clear()
        self.client_configs.clear()

        super().stop()
        logger.info("GRPC clients stopped")

    def _create_client(self, name: str, config: GRPCClientConfig):
        """创建单个GRPC客户端"""
        try:
            logger.info(f"Creating GRPC client: {name} -> {config.host}:{config.port}")

            # 构建连接地址
            target = f"{config.host}:{config.port}"

            # 设置连接选项
            options = [
                ('grpc.max_receive_message_length', config.max_receive_message_length),
                ('grpc.max_send_message_length', config.max_send_message_length),
            ]

            # 添加keepalive选项
            if config.keepalive_options:
                for key, value in config.keepalive_options.items():
                    options.append((key, value))

            # 创建通道
            if config.secure:
                if config.credentials_path:
                    with open(config.credentials_path, 'rb') as f:
                        credentials = grpc.ssl_channel_credentials(f.read())
                else:
                    credentials = grpc.ssl_channel_credentials()

                channel = grpc.secure_channel(target, credentials, options=options)
            else:
                channel = grpc.insecure_channel(target, options=options)

            # 存储客户端和配置
            self.clients[name] = channel
            self.client_configs[name] = config

            logger.info(f"GRPC client created successfully: {name}")

        except Exception as e:
            logger.error(f"Failed to create GRPC client {name}: {str(e)}")
            raise

    def get_client(self, name: str) -> Optional[grpc.Channel]:
        """获取指定名称的GRPC客户端"""
        channel = self.clients.get(name)
        if not channel:
            logger.warning(f"GRPC client not found: {name}")
        return channel

    def get_stub(self, name: str, stub_class):
        """获取指定名称的GRPC Stub"""
        channel = self.get_client(name)
        if channel:
            return stub_class(channel)
        return None

    def add_client(self, name: str, config: GRPCClientConfig):
        """动态添加GRPC客户端"""
        if name in self.clients:
            logger.warning(f"GRPC client {name} already exists, replacing...")
            self.remove_client(name)

        self._create_client(name, config)

    def remove_client(self, name: str):
        """移除GRPC客户端"""
        if name in self.clients:
            try:
                self.clients[name].close()
                del self.clients[name]
                del self.client_configs[name]
                logger.info(f"GRPC client removed: {name}")
            except Exception as e:
                logger.error(f"Error removing GRPC client {name}: {str(e)}")

    def _start_health_check(self):
        """启动健康检查线程"""
        self.health_check_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="grpc-health")
        self.health_check_executor.submit(self._health_check_loop)

    def _health_check_loop(self):
        """健康检查循环"""
        logger.info("GRPC health check started")

        while not self.health_check_stop_event.is_set():
            try:
                for name, channel in self.clients.items():
                    self._check_client_health(name, channel)

                # 等待下次检查
                self.health_check_stop_event.wait(self.config.health_check_interval)

            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
                time.sleep(5)  # 出错后短暂等待

    def _check_client_health(self, name: str, channel: grpc.Channel):
        """检查单个客户端健康状态"""
        try:
            # 简单的连接状态检查
            state = channel.get_state(try_to_connect=False)

            if state in [grpc.ChannelConnectivity.TRANSIENT_FAILURE, grpc.ChannelConnectivity.SHUTDOWN]:
                logger.warning(f"GRPC client {name} connection issue: {state}")

                # 可以在这里实现重连逻辑
                if state == grpc.ChannelConnectivity.TRANSIENT_FAILURE:
                    logger.info(f"Attempting to reconnect GRPC client: {name}")

        except Exception as e:
            logger.error(f"Health check failed for {name}: {str(e)}")

    def health_check(self) -> bool:
        """组件健康检查"""
        if not super().health_check():
            return False

        # 检查是否有活跃的客户端
        healthy_clients = 0
        for name, channel in self.clients.items():
            try:
                state = channel.get_state(try_to_connect=False)
                if state == grpc.ChannelConnectivity.READY:
                    healthy_clients += 1
            except Exception:
                pass

        return healthy_clients > 0 if self.clients else True
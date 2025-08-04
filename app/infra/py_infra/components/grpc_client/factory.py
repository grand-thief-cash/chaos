# infra/pyinfra/components/grpc_client/factory.py
from typing import Dict
from components.grpc_client.component import GRPCClientComponent
from components.grpc_client.schema import GRPCClientsConfig, GRPCClientConfig
from core.container import Container
import logging

logger = logging.getLogger(__name__)


def create_and_register_grpc_clients(config: Dict) -> GRPCClientComponent:
    """创建并注册GRPC客户端组件"""

    # 解析配置
    grpc_config_dict = config.get("grpc_clients", {})

    # 转换客户端配置
    clients_config = {}
    for name, client_config in grpc_config_dict.get("clients", {}).items():
        clients_config[name] = GRPCClientConfig(**client_config, name=name)

    # 创建主配置
    grpc_clients_config = GRPCClientsConfig(
        clients=clients_config,
        **{k: v for k, v in grpc_config_dict.items() if k != "clients"}
    )

    # 创建组件
    component = GRPCClientComponent(grpc_clients_config)

    # 注册到容器
    Container.register("grpc_clients", component)

    # 注册到生命周期管理
    from core.lifecycle import LifecycleManager
    LifecycleManager.register_component(component)

    logger.info(f"GRPC clients component registered with {len(clients_config)} clients")
    return component
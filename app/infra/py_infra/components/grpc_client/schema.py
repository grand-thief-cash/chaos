# infra/pyinfra/components/grpc_client/schema.py
from core.component import ComponentConfig
from typing import Dict, Optional
from pydantic import Field

class GRPCClientConfig(ComponentConfig):
    """单个GRPC客户端配置"""
    name: str
    host: str
    port: int
    secure: bool = False
    credentials_path: Optional[str] = None
    max_receive_message_length: int = 4 * 1024 * 1024  # 4MB
    max_send_message_length: int = 4 * 1024 * 1024     # 4MB
    compression: Optional[str] = None  # 'gzip' or None
    timeout: int = 30
    retry_policy: Optional[Dict] = None
    keepalive_options: Optional[Dict] = None

class GRPCClientsConfig(ComponentConfig):
    """多GRPC客户端配置"""
    clients: Dict[str, GRPCClientConfig] = Field(default_factory=dict)
    default_timeout: int = 30
    enable_health_check: bool = True
    health_check_interval: int = 60
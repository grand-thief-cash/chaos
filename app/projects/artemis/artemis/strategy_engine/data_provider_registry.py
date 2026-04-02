from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class DataProviderSpec:
    """数据源规格，定义回测数据提供者的配置和字段要求。"""
    code: str
    supported_modes: tuple[str, ...] = ("historical",)
    supported_timeframes: tuple[str, ...] = ("daily",)
    default_adjust: str = "nf"
    required_fields: tuple[str, ...] = (
        "date",
        "code",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    )
    config_schema: Dict[str, Any] = field(default_factory=dict)


class DataProviderRegistry:
    """数据源注册表，管理所有可用的数据提供者规格。"""

    def __init__(self) -> None:
        self._registry: Dict[str, DataProviderSpec] = {}

    def register(self, spec: DataProviderSpec) -> None:
        self._registry[spec.code] = spec

    def get(self, code: str) -> DataProviderSpec | None:
        return self._registry.get(str(code).strip())

    def require(self, code: str) -> DataProviderSpec:
        spec = self.get(code)
        if not spec:
            raise ValueError(f"data_provider_code '{code}' is not registered")
        return spec


_data_provider_spec = DataProviderSpec(code="phoenixa_hist_daily")
data_provider_registry = DataProviderRegistry()
data_provider_registry.register(_data_provider_spec)


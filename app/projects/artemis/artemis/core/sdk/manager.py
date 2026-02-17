from typing import Any, Dict

from artemis.consts import SDK_NAME
from artemis.core.config_manager import cfg_mgr
from artemis.core.sdk.amazing_data_sdk import AmazingDataSDK
from artemis.core.sdk.baostock_sdk import BaostockSDK
from artemis.core.sdk.base import BaseSDK


class SDKManager:
    """
    Central manager for SDK instances.
    It reads config and instantiates requested SDKs as Singletons.
    """
    _instance = None
    _sdks: Dict[str, BaseSDK] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SDKManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Read 'sdk' section from global config
        # cfg_mgr.get_config() is now updated to include sdk field.
        pass

    def get_sdk(self, name: SDK_NAME) -> Any:
        if name not in self._sdks:
            self._load_sdk(name)

        sdk = self._sdks.get(name)
        if not sdk:
            raise ValueError(f"SDK '{name}' not found or configured")

        return sdk.get_client()

    def _load_sdk(self, name: str):
        # Lazy load approach
        sdk_configs = cfg_mgr.get_config().sdk or {}

        if name == SDK_NAME.BAOSTOCK:
            self._sdks[name] = BaostockSDK(sdk_configs.get('baostock', {}))
        elif name == SDK_NAME.AMAZING_DATA:
            self._sdks[name] = AmazingDataSDK(sdk_configs.get('amazing_data', {}))
        else:
            raise ValueError(f"Unknown SDK: {name}")

sdk_mgr = SDKManager()

from artemis.core.config_manager import cfg_mgr
from artemis.core.context import TaskContext
from artemis.core.sdk.manager import sdk_mgr
from artemis.core.task_registry import registry

# Singleton instance (reuse from config_manager module)
__all__ = ["TaskContext", "cfg_mgr", "registry", "sdk_mgr"]

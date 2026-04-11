"""Cache engine module — 本地 Arrow 缓存，为 Workbench 提供低延迟数据读取。"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from artemis.engines.cache_engine.cache_engine import CacheEngine

_cache_engine: Optional[CacheEngine] = None
_init_lock = threading.Lock()


def get_cache_engine() -> Optional[CacheEngine]:
    """延迟初始化的 CacheEngine 单例。未启用时返回 None。"""
    global _cache_engine
    if _cache_engine is not None:
        return _cache_engine

    with _init_lock:
        if _cache_engine is not None:
            return _cache_engine

        try:
            from artemis.core import cfg_mgr
            engine_cfg = cfg_mgr.engine_config()
        except Exception:
            return None

        if not engine_cfg or not hasattr(engine_cfg, "cache_engine"):
            return None

        cache_cfg = engine_cfg.cache_engine
        if not cache_cfg or not cache_cfg.enabled:
            return None

        from artemis.engines.cache_engine.cache_engine import CacheEngine
        from artemis.log.logger import get_logger

        _cache_engine = CacheEngine(cache_cfg)
        logger = get_logger("cache_engine_init")
        logger.info({"event": "cache_engine_created", "cache_dir": cache_cfg.cache_dir})
        return _cache_engine


def reset_cache_engine() -> None:
    """重置单例（仅用于测试）。"""
    global _cache_engine
    with _init_lock:
        _cache_engine = None

# pyinfra/hooks/__init__.py
from ..core.lifecycle import LifecycleManager

def register_hook(phase: str):
    """装饰器注册生命周期钩子"""
    def decorator(func):
        LifecycleManager.add_hook(phase, func)
        return func
    return decorator
from typing import Type, Dict

_REGISTRY: Dict[str, Type] = {}

def register(task_code: str, cls: Type):
    if task_code in _REGISTRY:
        raise ValueError(f"Task '{task_code}' already registered")
    _REGISTRY[task_code] = cls

def get(task_code: str):
    return _REGISTRY.get(task_code)

def list_tasks():
    return list(_REGISTRY.keys())


# pyinfra/core/container.py

from typing import Any, Dict

class Container:
    _components: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, instance: Any):
        cls._components[name] = instance

    @classmethod
    def resolve(cls, name: str) -> Any:
        return cls._components.get(name)

    @classmethod
    def unregister(cls, name: str):
        cls._components.pop(name, None)

    @classmethod
    def list_registered(cls) -> Dict[str, Any]:
        return dict(cls._components)

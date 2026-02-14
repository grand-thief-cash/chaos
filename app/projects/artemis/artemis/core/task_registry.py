import importlib
import sys
from dataclasses import dataclass
from typing import Type, Dict, Optional

from artemis.consts import TaskCode


@dataclass(frozen=True)
class TaskSpec:
    module: str
    class_name: str

    def resolve(self) -> Type:
        module = importlib.import_module(self.module)
        if module.__name__ in sys.modules:
            module = importlib.reload(module)
        try:
            return getattr(module, self.class_name)
        except AttributeError as exc:
            raise ValueError(f"Task class '{self.class_name}' not found in module '{self.module}'") from exc


class TaskRegistry:
    def __init__(self):
        self._registry: Dict[str, TaskSpec] = {}

    @staticmethod
    def _normalize_key(task_code: TaskCode | str) -> str:
        if isinstance(task_code, TaskCode):
            key = task_code.value
        else:
            key = str(task_code)
        key = key.strip()
        if not key:
            raise ValueError("task_code cannot be empty")
        return key

    def register(
        self,
        task_code: TaskCode | str,
        cls: Optional[Type] = None,
        module: Optional[str] = None,
        class_name: Optional[str] = None,
    ):
        key = self._normalize_key(task_code)
        if key in self._registry:
            raise ValueError(f"Task '{key}' already registered")

        if cls is not None:
            spec = TaskSpec(module=cls.__module__, class_name=cls.__name__)
        else:
            if not module or not class_name:
                raise ValueError("register requires either cls or module+class_name")
            spec = TaskSpec(module=module, class_name=class_name)

        self._registry[key] = spec

    def has_task(self, task_code: TaskCode | str) -> bool:
        key = self._normalize_key(task_code)
        return key in self._registry

    def get_task_spec(self, task_code: TaskCode | str) -> Optional[TaskSpec]:
        key = self._normalize_key(task_code)
        return self._registry.get(key)

    def get_task(self, task_code: TaskCode | str):
        spec = self.get_task_spec(task_code)
        if not spec:
            return None
        return spec.resolve()

    def list_tasks(self) -> Dict[str, TaskSpec]:
        """Return a shallow copy of the registry mapping task code to task spec."""
        return dict(self._registry)


registry = TaskRegistry()

from typing import Type, Dict

from artemis.consts import TaskCode


class TaskRegistry:
    def __init__(self):
        self._registry: Dict[TaskCode, Type] = {}

    def register(self, task_code: TaskCode, cls: Type):
        if task_code in self._registry:
            raise ValueError(f"Task '{task_code}' already registered")
        self._registry[task_code] = cls

    def get_task(self, task_code: TaskCode):
        return self._registry.get(task_code)

    def list_tasks(self):
        return list(self._registry.keys())
registry = TaskRegistry()

from artemis.core.context import TaskContext
from typing import Iterable, Any


class BaseSource:
    def fetch(self, params: dict, ctx: TaskContext) -> Iterable[Any]:
        raise NotImplementedError


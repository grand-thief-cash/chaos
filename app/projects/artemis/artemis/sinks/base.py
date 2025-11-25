from artemis.core.context import TaskContext
from typing import List, Any


class BaseSink:
    def emit(self, batch: List[Any], ctx: TaskContext):
        raise NotImplementedError


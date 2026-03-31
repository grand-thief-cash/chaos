from .base import BaseTaskUnit


class WorkerUnit(BaseTaskUnit):
    """
    Standard worker task unit.
    For semantic clarity: Tasks inherited from this are leaf nodes.
    Currently identical behavior to BaseTaskUnit.
    """
    pass

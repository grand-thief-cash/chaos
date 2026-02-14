from artemis.consts import TaskCode
from artemis.core import registry
from artemis.task_units.base import BaseTaskUnit
from artemis.task_units.child import ChildTaskUnit
from artemis.task_units.parent import OrchestratorTaskUnit
from artemis.task_units.zh import StockZHAListDailyTask

__all__ = ['BaseTaskUnit', 'OrchestratorTaskUnit', 'ChildTaskUnit']

registry.register(
    TaskCode.STOCK_ZH_A_LIST,
    module=StockZHAListDailyTask.__module__,
    class_name=StockZHAListDailyTask.__name__,
)

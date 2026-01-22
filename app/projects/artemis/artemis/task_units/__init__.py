from artemis.consts import TaskCode
from artemis.core import registry
from artemis.task_units.base import BaseTaskUnit
from artemis.task_units.child import ChildTaskUnit
from artemis.task_units.parent import ParentTaskUnit
from artemis.task_units.zh import StockZHAListDailyTask

__all__ = ['BaseTaskUnit', 'ParentTaskUnit', 'ChildTaskUnit']

registry.register(TaskCode.STOCK_ZH_A_LIST, StockZHAListDailyTask)

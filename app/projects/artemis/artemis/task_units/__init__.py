from artemis.core import task_registry
from artemis.task_units.base import BaseTaskUnit
from artemis.task_units.child import ChildTaskUnit
from artemis.task_units.parent import ParentTaskUnit
from artemis.task_units.security_ZH.stock_a_list.stock_a_list import StockAListDailyTask

__all__ = ['BaseTaskUnit', 'ParentTaskUnit', 'ChildTaskUnit']


task_registry.register("stock_a_list", StockAListDailyTask)


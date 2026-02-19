from artemis.consts import TaskCode
from artemis.core import registry
from artemis.task_units.base import BaseTaskUnit
from artemis.task_units.child import ChildTaskUnit
from artemis.task_units.download.zh import StockZhAHistParent, StockZhAHistChild
from artemis.task_units.download.zh.stock_zh_a_list import StockZHAList
from artemis.task_units.parent import OrchestratorTaskUnit

__all__ = ['BaseTaskUnit', 'OrchestratorTaskUnit', 'ChildTaskUnit']

registry.register(
    TaskCode.STOCK_ZH_A_LIST,
    module=StockZHAList.__module__,
    class_name=StockZHAList.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_HIST_PARENT,
    module=StockZhAHistParent.__module__,
    class_name=StockZhAHistParent.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_HIST_CHILD,
    module=StockZhAHistChild.__module__,
    class_name=StockZhAHistChild.__name__,
)

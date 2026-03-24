from artemis.task_units.child import WorkerUnit
from artemis.task_units.parent import OrchestratorUnit

from artemis.consts import TaskCode
from artemis.core import registry
from artemis.task_units.base import BaseTaskUnit
from artemis.task_units.download.zh import StockZhAHistParent, StockZhAHistChild, StockZHAMarketCategory
from artemis.task_units.download.zh.stock_zh_a_list import StockZHAList

__all__ = ['BaseTaskUnit', 'OrchestratorUnit', 'WorkerUnit']

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

registry.register(
    TaskCode.STOCK_ZH_A_MKT_CATEGORY,
    module=StockZHAMarketCategory.__module__,
    class_name=StockZHAMarketCategory.__name__
)
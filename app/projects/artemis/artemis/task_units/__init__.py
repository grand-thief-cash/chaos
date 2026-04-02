from artemis.task_units.worker_unit import WorkerUnit
from artemis.task_units.orchestrator_unit import OrchestratorUnit

from artemis.consts import TaskCode
from artemis.core import registry
from artemis.task_units.base import BaseTaskUnit
from artemis.task_units.bt_engine import BacktraderCampaignTask, BacktraderRunTask
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

registry.register(
    TaskCode.BACKTRADER_CAMPAIGN,
    module=BacktraderCampaignTask.__module__,
    class_name=BacktraderCampaignTask.__name__,
)

registry.register(
    TaskCode.BACKTRADER_RUN,
    module=BacktraderRunTask.__module__,
    class_name=BacktraderRunTask.__name__,
)

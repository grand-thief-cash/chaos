from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit

from artemis.consts import TaskCode
from artemis.core import registry
from artemis.engines.task_engine.base import BaseTaskUnit
from artemis.engines.task_engine.backtest import BacktraderCampaignTask, BacktraderRunTask
from artemis.engines.task_engine.download.zh import StockZhAHistParent, StockZhAHistChild, StockZHAMarketCategory
from artemis.engines.task_engine.download.zh.stock_zh_a_list import StockZHAList

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

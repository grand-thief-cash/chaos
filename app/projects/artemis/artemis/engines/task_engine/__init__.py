from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit

from artemis.consts import TaskCode
from artemis.core import registry
from artemis.engines.task_engine.base import BaseTaskUnit
from artemis.engines.task_engine.backtest import BacktraderCampaignTask, BacktraderRunTask
from artemis.engines.task_engine.download.zh import StockZhAHistParent, StockZhAHistChild, StockZHAMarketCategory, StockZHAMarketCategorySWHY
from artemis.engines.task_engine.download.zh.stock_zh_a_list import StockZHAList
from artemis.engines.task_engine.download.zh.stock_zh_a_industry_constituent_swhy import StockZHAIndustryConstituentSWHY
from artemis.engines.task_engine.download.zh.stock_zh_a_industry_weight_swhy import StockZHAIndustryWeightSWHY
from artemis.engines.task_engine.download.zh.stock_zh_a_industry_daily_swhy import StockZHAIndustryDailySWHY

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
    TaskCode.STOCK_ZH_A_MKT_CATEGORY_SWHY,
    module=StockZHAMarketCategorySWHY.__module__,
    class_name=StockZHAMarketCategorySWHY.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY,
    module=StockZHAIndustryConstituentSWHY.__module__,
    class_name=StockZHAIndustryConstituentSWHY.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY,
    module=StockZHAIndustryWeightSWHY.__module__,
    class_name=StockZHAIndustryWeightSWHY.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_INDUSTRY_DAILY_SWHY,
    module=StockZHAIndustryDailySWHY.__module__,
    class_name=StockZHAIndustryDailySWHY.__name__,
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

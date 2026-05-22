from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit

from artemis.consts import TaskCode
from artemis.core import registry
from artemis.engines.task_engine.base import BaseTaskUnit
from artemis.engines.task_engine.backtest import BacktraderCampaignTask, BacktraderRunTask
from artemis.engines.task_engine.download.zh import (
    StockZhAHistParent, StockZhAHistChild,
    StockZHAMktCategoryMairui, StockZHAMarketCategorySWHY,
    StockZHAIndustryWeightSWHY, StockZHAIndustryWeightSWHYChild,
    StockZHAIndustryDailySWHY, StockZHAIndustryDailySWHYChild,
    StockZhABsBalanceParent, StockZhABsBalanceChild,
    StockZhABsDividendParent, StockZhABsDividendChild,
    StockZhABsAdjustFactorParent, StockZhABsAdjustFactorChild,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_list import StockZHAList
from artemis.engines.task_engine.download.zh.stock_zh_a_industry_constituent_swhy import StockZHAIndustryConstituentSWHY
from artemis.engines.task_engine.download.zh.stock_zh_a_balance_sheet import StockZHABalanceSheet
from artemis.engines.task_engine.download.zh.stock_zh_a_cash_flow import StockZHACashFlow
from artemis.engines.task_engine.download.zh.stock_zh_a_income import StockZHAIncome
from artemis.engines.task_engine.download.zh.stock_zh_a_profit_express import StockZHAProfitExpress
from artemis.engines.task_engine.download.zh.stock_zh_a_profit_notice import StockZHAProfitNotice
from artemis.engines.task_engine.download.zh.stock_zh_a_dividend import StockZHADividend
from artemis.engines.task_engine.download.zh.stock_zh_a_right_issue import StockZHARightIssue

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
    TaskCode.STOCK_ZH_A_MKT_CATEGORY_MAIRUI,
    module=StockZHAMktCategoryMairui.__module__,
    class_name=StockZHAMktCategoryMairui.__name__
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
    TaskCode.STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY_CHILD,
    module=StockZHAIndustryWeightSWHYChild.__module__,
    class_name=StockZHAIndustryWeightSWHYChild.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_INDUSTRY_DAILY_SWHY,
    module=StockZHAIndustryDailySWHY.__module__,
    class_name=StockZHAIndustryDailySWHY.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_INDUSTRY_DAILY_SWHY_CHILD,
    module=StockZHAIndustryDailySWHYChild.__module__,
    class_name=StockZHAIndustryDailySWHYChild.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_BALANCE_SHEET,
    module=StockZHABalanceSheet.__module__,
    class_name=StockZHABalanceSheet.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_CASH_FLOW,
    module=StockZHACashFlow.__module__,
    class_name=StockZHACashFlow.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_INCOME,
    module=StockZHAIncome.__module__,
    class_name=StockZHAIncome.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_PROFIT_EXPRESS,
    module=StockZHAProfitExpress.__module__,
    class_name=StockZHAProfitExpress.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_PROFIT_NOTICE,
    module=StockZHAProfitNotice.__module__,
    class_name=StockZHAProfitNotice.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_DIVIDEND,
    module=StockZHADividend.__module__,
    class_name=StockZHADividend.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_RIGHT_ISSUE,
    module=StockZHARightIssue.__module__,
    class_name=StockZHARightIssue.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_BS_BALANCE_PARENT,
    module=StockZhABsBalanceParent.__module__,
    class_name=StockZhABsBalanceParent.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_BS_BALANCE_CHILD,
    module=StockZhABsBalanceChild.__module__,
    class_name=StockZhABsBalanceChild.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_BS_DIVIDEND_PARENT,
    module=StockZhABsDividendParent.__module__,
    class_name=StockZhABsDividendParent.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_BS_DIVIDEND_CHILD,
    module=StockZhABsDividendChild.__module__,
    class_name=StockZhABsDividendChild.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_BS_ADJUST_FACTOR_PARENT,
    module=StockZhABsAdjustFactorParent.__module__,
    class_name=StockZhABsAdjustFactorParent.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_BS_ADJUST_FACTOR_CHILD,
    module=StockZhABsAdjustFactorChild.__module__,
    class_name=StockZhABsAdjustFactorChild.__name__,
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

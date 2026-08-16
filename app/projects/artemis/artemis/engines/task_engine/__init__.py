from importlib import import_module

from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.orchestrator_unit import OrchestratorUnit

from artemis.consts import TaskCode
from artemis.core import registry
from artemis.engines.task_engine.base import BaseTaskUnit
from artemis.engines.task_engine.download.zh import (
    StockZhAHistParent, StockZhAHistChild,
    StockZhAMinuteParent, StockZhAMinuteChild,
    StockZhAKlineParent, StockZhAKlineChild,
    IndexZhAKlineParent, IndexZhAKlineChild,
    StockZhALevel1File,
    StockZHAMktCategoryMairui, StockZHAMarketCategorySWHY,
    StockZHAIndustryWeightSWHY, StockZHAIndustryWeightSWHYChild,
    StockZHAIndustryDailySWHY, StockZHAIndustryDailySWHYChild,
    StockZhABsBalanceParent, StockZhABsBalanceChild,
    StockZhABsDividendParent, StockZhABsDividendChild,
    StockZhABsAdjustFactorParent, StockZhABsAdjustFactorChild,
    StockZHALongHuBang, IndexZhADaily,
    IndexZhAOptionQVIX, OptionZhADailyStats,
    StockZhAHsgtHist, StockZhAMarginSummary,
    StockZhANotice, StockZhADisclosureSchedule,
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
from artemis.engines.task_engine.download.zh.stock_zh_a_eastmoney_report import (
    EastmoneyResearchReport,
)
from artemis.feature_platform.tasks.feature_compute_task import FeatureComputeTask
from artemis.engines.task_engine.download.us.stock_us_daily import StockUSDaily
from artemis.engines.task_engine.download.us.stock_us_list import StockUSList

GlobalCommodityDaily = import_module(
    "artemis.engines.task_engine.download.global.commodity_daily",
).GlobalCommodityDaily
GlobalFxDaily = import_module(
    "artemis.engines.task_engine.download.global.fx_daily",
).GlobalFxDaily
GlobalIndexDaily = import_module(
    "artemis.engines.task_engine.download.global.index_daily",
).GlobalIndexDaily
GlobalRateDaily = import_module(
    "artemis.engines.task_engine.download.global.rate_daily",
).GlobalRateDaily
GlobalSecurityList = import_module(
    "artemis.engines.task_engine.download.global.security_list",
).GlobalSecurityList

__all__ = ['BaseTaskUnit', 'OrchestratorUnit', 'WorkerUnit']

registry.register(
    TaskCode.FEATURE_PLATFORM_COMPUTE,
    module=FeatureComputeTask.__module__,
    class_name=FeatureComputeTask.__name__,
)

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
    TaskCode.STOCK_ZH_A_MINUTE_PARENT,
    module=StockZhAMinuteParent.__module__,
    class_name=StockZhAMinuteParent.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_MINUTE_CHILD,
    module=StockZhAMinuteChild.__module__,
    class_name=StockZhAMinuteChild.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_KLINE_PARENT,
    module=StockZhAKlineParent.__module__,
    class_name=StockZhAKlineParent.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_KLINE_CHILD,
    module=StockZhAKlineChild.__module__,
    class_name=StockZhAKlineChild.__name__,
)

registry.register(
    TaskCode.INDEX_ZH_A_KLINE_PARENT,
    module=IndexZhAKlineParent.__module__,
    class_name=IndexZhAKlineParent.__name__,
)

registry.register(
    TaskCode.INDEX_ZH_A_KLINE_CHILD,
    module=IndexZhAKlineChild.__module__,
    class_name=IndexZhAKlineChild.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_LEVEL1_FILE,
    module=StockZhALevel1File.__module__,
    class_name=StockZhALevel1File.__name__,
)

registry.register(
    TaskCode.INDEX_ZH_A_DAILY,
    module=IndexZhADaily.__module__,
    class_name=IndexZhADaily.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_MARGIN_SUMMARY,
    module=StockZhAMarginSummary.__module__,
    class_name=StockZhAMarginSummary.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_HSGT_HIST,
    module=StockZhAHsgtHist.__module__,
    class_name=StockZhAHsgtHist.__name__,
)

registry.register(
    TaskCode.INDEX_ZH_A_OPTION_QVIX,
    module=IndexZhAOptionQVIX.__module__,
    class_name=IndexZhAOptionQVIX.__name__,
)

registry.register(
    TaskCode.OPTION_ZH_A_DAILY_STATS,
    module=OptionZhADailyStats.__module__,
    class_name=OptionZhADailyStats.__name__,
)

registry.register(
    TaskCode.GLOBAL_SECURITY_LIST,
    module=GlobalSecurityList.__module__,
    class_name=GlobalSecurityList.__name__,
)

registry.register(
    TaskCode.GLOBAL_INDEX_DAILY,
    module=GlobalIndexDaily.__module__,
    class_name=GlobalIndexDaily.__name__,
)

registry.register(
    TaskCode.GLOBAL_RATE_DAILY,
    module=GlobalRateDaily.__module__,
    class_name=GlobalRateDaily.__name__,
)

registry.register(
    TaskCode.GLOBAL_FX_DAILY,
    module=GlobalFxDaily.__module__,
    class_name=GlobalFxDaily.__name__,
)

registry.register(
    TaskCode.GLOBAL_COMMODITY_DAILY,
    module=GlobalCommodityDaily.__module__,
    class_name=GlobalCommodityDaily.__name__,
)

registry.register(
    TaskCode.STOCK_US_LIST,
    module=StockUSList.__module__,
    class_name=StockUSList.__name__,
)

registry.register(
    TaskCode.STOCK_US_DAILY,
    module=StockUSDaily.__module__,
    class_name=StockUSDaily.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_NOTICE,
    module=StockZhANotice.__module__,
    class_name=StockZhANotice.__name__,
)

registry.register(
    TaskCode.STOCK_ZH_A_DISCLOSURE_SCHEDULE,
    module=StockZhADisclosureSchedule.__module__,
    class_name=StockZhADisclosureSchedule.__name__,
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
    TaskCode.STOCK_ZH_A_LONG_HU_BANG,
    module=StockZHALongHuBang.__module__,
    class_name=StockZHALongHuBang.__name__,
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
    TaskCode.EASTMONEY_RESEARCH_REPORT,
    module=EastmoneyResearchReport.__module__,
    class_name=EastmoneyResearchReport.__name__,
)

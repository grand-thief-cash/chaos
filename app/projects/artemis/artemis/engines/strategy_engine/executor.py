"""回测核心执行函数，供 Workbench 和 TaskEngine 两条路径共用。

消除了 services/workbench/backtest.py 和 task_engine/backtest/run.py 之间的重复逻辑：
  - _extract_analyzer_results 只有一份实现
  - 引擎构建 → 执行 → 提取结果 统一在 execute_backtest()
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd

from artemis.engines.strategy_engine.analyzers.registry_map import AnalyzerProfileSpec
from artemis.engines.strategy_engine.engine_builder import BacktraderEngineBuilder
from artemis.engines.strategy_engine.strategy_registry import StrategySpec

logger = logging.getLogger(__name__)


def extract_analyzer_results(strategy_instance: Any) -> Dict[str, Any]:
    """从策略实例中提取分析器结果，返回 {name: analysis} 字典。

    这是唯一的实现，Workbench 和 TaskEngine 共用。
    """
    analyzers = getattr(strategy_instance, "analyzers", None)
    if analyzers is None:
        return {}
    try:
        items = analyzers.getitems()
    except Exception:
        logger.warning("failed to extract analyzer results", exc_info=True)
        return {}
    return {name: analyzer.get_analysis() for name, analyzer in items}


def execute_backtest(
    *,
    df: pd.DataFrame,
    strategy_spec: StrategySpec,
    strategy_params: Dict[str, Any],
    analyzer_profile: AnalyzerProfileSpec,
    cash: float,
    commission: float,
) -> Dict[str, Any]:
    """执行一次回测，返回原始结果字典。

    这是 Workbench 和 TaskEngine 共用的核心执行逻辑。
    调用方拿到返回值后，再各自调用 BacktestResultNormalizer.normalize() 标准化。

    Args:
        df: OHLCV K 线 DataFrame（至少含 date/open/high/low/close 列）。
        strategy_spec: 策略规格。
        strategy_params: 已合并 default + user 的策略参数。
        analyzer_profile: 分析器配置。
        cash: 初始资金。
        commission: 手续费率。

    Returns:
        {
            "strategy_instance": bt.Strategy 实例,
            "analyzer_results": {name: analysis},
            "bars_processed": int,
            "start_cash": float,
            "end_value": float,
        }
    """
    cerebro = BacktraderEngineBuilder.build(
        df=df,
        strategy_spec=strategy_spec,
        strategy_params=strategy_params,
        analyzer_profile=analyzer_profile,
        cash=cash,
        commission=commission,
    )
    start_cash = float(cerebro.broker.get_cash())
    strategies = cerebro.run()
    strategy_instance = strategies[0]
    analyzer_results = extract_analyzer_results(strategy_instance)
    end_value = float(cerebro.broker.get_value())
    bars_processed = len(df.index)

    return {
        "strategy_instance": strategy_instance,
        "analyzer_results": analyzer_results,
        "bars_processed": bars_processed,
        "start_cash": start_cash,
        "end_value": end_value,
    }


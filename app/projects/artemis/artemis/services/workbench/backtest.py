"""策略研发工作台服务，提供轻量级交互式回测能力，直接调用 strategy_engine。"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pandas as pd

from artemis.engines.strategy_engine import analyzer_profile_registry, strategy_registry
from artemis.engines.strategy_engine.executor import execute_backtest
from artemis.engines.strategy_engine.result_normalizer import BacktestResultNormalizer
from artemis.log.logger import get_logger
from artemis.models.workbench import WorkbenchRunReq

logger = get_logger("workbench")


def list_strategies() -> Dict[str, Any]:
    """返回所有可用策略及其参数 schema，供前端动态渲染表单。"""
    strategies: List[Dict[str, Any]] = []
    for code, spec in strategy_registry._registry.items():
        strategies.append(
            {
                "code": spec.code,
                "default_params": dict(spec.default_params),
                "supported_modes": list(spec.supported_modes),
                "supported_periods": list(spec.supported_timeframes),
                "param_schema": dict(spec.param_schema),
            }
        )
    return {"strategies": strategies}


def run_backtest(req: WorkbenchRunReq) -> Dict[str, Any]:
    """执行一次轻量回测，直接返回结果 JSON，不落库。"""
    # 1. 校验策略
    spec = strategy_registry.require(req.strategy_code)

    # 2. 校验策略参数
    errors = spec.validate_params(req.strategy_params)
    if errors:
        raise ValueError("; ".join(errors))

    # 3. 校验时间范围
    if req.start_date > req.end_date:
        raise ValueError("start_date must be <= end_date")

    # 4. 获取 analyzer profile（MVP 硬编码）
    analyzer_profile = analyzer_profile_registry.require("default_hist_v1")

    # 5. 通过 market_data 服务获取数据（支持缓存 + provider 路由）
    from artemis.services.workbench.market_data import get_market_bars

    market_resp = get_market_bars(
        symbol=req.symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        period=req.period,
        adjust=req.adjust,
        asset_type=req.asset_type,
        market=req.market,
        source=req.source,
        use_cache=req.use_cache,
    )
    bars = market_resp["bars"]
    if not bars:
        raise ValueError(
            f"无法获取数据: symbol={req.symbol}, asset_type={req.asset_type}, market={req.market}, period={req.period}, adjust={req.adjust}。请检查数据维度组合是否有对应数据。"
        )

    # 6. 执行回测（共用核心执行函数）
    df = pd.DataFrame(bars)
    merged_params = {**spec.default_params, **req.strategy_params}
    result = execute_backtest(
        df=df,
        strategy_spec=spec,
        strategy_params=merged_params,
        analyzer_profile=analyzer_profile,
        cash=req.cash,
        commission=req.commission,
    )

    # 7. 标准化结果
    run_id = f"wb-{int(time.time())}"
    normalized = BacktestResultNormalizer.normalize(
        run_id=run_id,
        parent_run_id=None,
        task_code="workbench",
        mode="historical",
        strategy_code=req.strategy_code,
        symbol=req.symbol,
        period=req.period,
        start_date=req.start_date,
        end_date=req.end_date,
        start_cash=result["start_cash"],
        end_value=result["end_value"],
        strategy_instance=result["strategy_instance"],
        analyzer_results=result["analyzer_results"],
        bars_processed=result["bars_processed"],
    )

    summary = dict(normalized["summary"])

    # Include original bars in artifacts so frontend can render K-line chart with B/S markers
    normalized["artifacts"]["bars"] = bars

    return {
        **normalized,
        "summary": summary,
    }

"""市场数据服务，封装 PhoenixAClient 获取 OHLCV K 线数据。"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.log.logger import get_logger

logger = get_logger("market_data_service")


def _build_phoenix_client() -> PhoenixAClient:
    """从配置构建 PhoenixAClient。"""
    dept = cfg_mgr.dept_services_config()
    if not dept or not dept.phoenixA:
        raise ValueError("phoenixA service not configured")
    cfg = dept.phoenixA
    return PhoenixAClient(
        host=cfg.host,
        port=cfg.port,
        logger=logger,
        timeout_seconds=getattr(cfg, "timeout_seconds", 30),
    )


def _sanitize_value(v: Any) -> Any:
    """将 NaN/inf 替换为 None，确保 JSON 可序列化。"""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _sanitize_bars(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """清洗 bars 数据中的 NaN/inf 值。"""
    return [{k: _sanitize_value(v) for k, v in bar.items()} for bar in bars]


def get_market_bars(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "daily",
    adjust: str = "nf",
) -> Dict[str, Any]:
    """获取 K 线 OHLCV 数据。

    Returns:
        {"symbol", "timeframe", "start_date", "end_date", "bars": [...]}
    """
    client = _build_phoenix_client()
    bars = client.get_strategy_market_bars(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        adjust=adjust,
    )
    if not bars:
        raise ValueError(f"no historical bars found for symbol={symbol}")

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "bars": _sanitize_bars(bars),
    }

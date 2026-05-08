"""Regime 计算服务。"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from artemis.engines.regime_engine.config import RegimeConfig
from artemis.engines.regime_engine.pipeline import RegimePipeline, RegimeDataProvider
from artemis.engines.regime_engine.storage.regime_store import RegimeStore
from artemis.log.logger import get_logger

logger = get_logger("regime_service")


# ---------------------------------------------------------------------------
# Mock data provider
# ---------------------------------------------------------------------------

class MockRegimeDataProvider:
    """占位数据源 — 返回空/默认数据。"""

    def get_index_bars(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        logger.warning("MockRegimeDataProvider: returning empty index bars")
        return {s: pd.DataFrame() for s in symbols}

    def get_market_breadth(self, trade_date: str) -> Dict[str, float]:
        return {"above_ma20_pct": 0.5}

    def get_industry_daily(self, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()

    def get_turnover_stats(self, trade_date: str) -> Dict[str, float]:
        return {"turnover_ratio": 1.0}


# ---------------------------------------------------------------------------
# Service singleton
# ---------------------------------------------------------------------------

_store = RegimeStore()
_provider: RegimeDataProvider = MockRegimeDataProvider()
_pipeline = RegimePipeline(_provider, _store)


def compute_regime(trade_date: str, market: str = "zh_a") -> dict:
    """计算单日 regime。"""
    logger.info({"event": "regime_compute", "trade_date": trade_date})
    return _pipeline.run(trade_date)


def get_current(market: str = "zh_a") -> Optional[dict]:
    dates = _store.list_dates()
    if not dates:
        return None
    return _store.get_regime(dates[-1])


def get_history(limit: int = 60) -> List[dict]:
    return _store.get_history(limit)


def get_features(trade_date: str) -> Optional[dict]:
    return _store.get_features(trade_date)


def backfill(trading_dates: List[str]) -> dict:
    """批量回填。"""
    logger.info({"event": "regime_backfill", "count": len(trading_dates)})
    results = _pipeline.run_backfill(trading_dates)
    return {"status": "ok", "count": len(results)}


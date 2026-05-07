"""Shared fixtures for cache_engine unit tests."""

import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import List

import pandas as pd
import pytest

# 触发模块初始化，避免 artemis.core / artemis.log 循环导入
import artemis.engines.task_engine  # noqa: F401

from artemis.models.configs import CacheEngineCfg, PartitionRuleCfg


# ── 默认分区规则（与 config-home.yaml 一致）────────────────────

DEFAULT_PARTITION_RULES = [
    PartitionRuleCfg(match={"asset_type": "stock", "period": "daily"}, granularity="yearly"),
    PartitionRuleCfg(match={"asset_type": "stock", "period": "weekly"}, granularity="yearly"),
    PartitionRuleCfg(match={"asset_type": "stock", "period": "1min"}, granularity="monthly"),
    PartitionRuleCfg(match={"asset_type": "stock", "period": "5min"}, granularity="monthly"),
    PartitionRuleCfg(match={"asset_type": "index"}, granularity="yearly"),
    PartitionRuleCfg(match={}, granularity="yearly"),  # 兜底
]


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    """提供一个干净的临时缓存目录。"""
    cache_dir = tmp_path / "cache" / "artemis"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def cache_cfg(tmp_cache_dir: Path) -> CacheEngineCfg:
    """提供一个标准的 CacheEngineCfg（使用临时目录）。"""
    return CacheEngineCfg(
        enabled=True,
        cache_dir=str(tmp_cache_dir),
        max_cache_size="5GB",
        eviction_policy="lru",
        eviction_check_interval=100,
        partition_rules=DEFAULT_PARTITION_RULES,
    )


@pytest.fixture
def cache_cfg_monthly_only(tmp_cache_dir: Path) -> CacheEngineCfg:
    """只包含 monthly 分区规则的配置。"""
    return CacheEngineCfg(
        enabled=True,
        cache_dir=str(tmp_cache_dir),
        partition_rules=[
            PartitionRuleCfg(
                match={"asset_type": "stock", "period": "daily"},
                granularity="monthly",
            ),
        ],
    )


@pytest.fixture
def cache_cfg_no_rules(tmp_cache_dir: Path) -> CacheEngineCfg:
    """无分区规则（用于测试兜底行为或错误）。"""
    return CacheEngineCfg(
        enabled=True,
        cache_dir=str(tmp_cache_dir),
        partition_rules=[],
    )


@pytest.fixture
def cache_cfg_fallback_only(tmp_cache_dir: Path) -> CacheEngineCfg:
    """只有兜底规则的配置。"""
    return CacheEngineCfg(
        enabled=True,
        cache_dir=str(tmp_cache_dir),
        partition_rules=[
            PartitionRuleCfg(match={}, granularity="yearly"),
        ],
    )


# ── OHLCV DataFrame 生成器 ──────────────────────────────────────


def make_ohlcv_df(
    symbol: str = "000001",
    start: str = "2024-01-02",
    end: str = "2024-12-31",
    price_base: float = 10.0,
) -> pd.DataFrame:
    """生成一个模拟的 OHLCV DataFrame。

    只生成工作日（跳过周末），模拟真实交易日。
    """
    rows = []
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    current = start_d
    idx = 0
    while current <= end_d:
        # 跳过周末
        if current.weekday() < 5:
            price = price_base + idx * 0.1
            rows.append({
                "date": current.isoformat(),
                "code": symbol,
                "open": price,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price + (0.2 if idx % 5 == 0 else -0.1),
                "volume": 1000.0 + idx,
                "amount": 100000.0 + idx * 10,
            })
            idx += 1
        current += timedelta(days=1)

    return pd.DataFrame(rows)


def make_ohlcv_records(
    symbol: str = "000001",
    start: str = "2024-01-02",
    end: str = "2024-12-31",
    price_base: float = 10.0,
) -> List[dict]:
    """生成模拟的 OHLCV 记录列表（供 data_fetcher 返回）。"""
    return make_ohlcv_df(symbol, start, end, price_base).to_dict("records")


def make_single_day_df(symbol: str = "000001", day: str = "2024-06-15") -> pd.DataFrame:
    """生成只有一天数据的 DataFrame。"""
    return pd.DataFrame([{
        "date": day,
        "code": symbol,
        "open": 10.0,
        "high": 10.5,
        "low": 9.5,
        "close": 10.2,
        "volume": 1000.0,
        "amount": 100000.0,
    }])

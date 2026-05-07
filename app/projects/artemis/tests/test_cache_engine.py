"""CacheEngine 端到端单元测试。

覆盖：
- put + get 回环
- cache hit / miss
- data_fetcher 回源
- use_cache=False
- 日期切片
- 跨分区查询
- 增量写入
- 去重
- 空数据
- 无 data_fetcher
- 并发读写
- _group_by_partition
- _extract_year / _extract_month
- _get_inc_date
"""

import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import pytest

from artemis.engines.cache_engine.cache_engine import CacheEngine
from artemis.models.configs import CacheEngineCfg, PartitionRuleCfg

from tests.conftest import DEFAULT_PARTITION_RULES, make_ohlcv_df, make_ohlcv_records


# ═══════════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════════


def _make_engine(tmp_cache_dir: Path, rules=None) -> CacheEngine:
    """创建一个 CacheEngine 实例。"""
    cfg = CacheEngineCfg(
        enabled=True,
        cache_dir=str(tmp_cache_dir),
        partition_rules=rules or DEFAULT_PARTITION_RULES,
    )
    return CacheEngine(cfg)


def _simple_fetcher(
    symbol: str, period: str, start_date: str, end_date: str, adjust: str
) -> List[Dict[str, Any]]:
    """简单的 data_fetcher 实现，返回模拟数据。"""
    return make_ohlcv_records(symbol, start_date, end_date)


def _empty_fetcher(
    symbol: str, period: str, start_date: str, end_date: str, adjust: str
) -> List[Dict[str, Any]]:
    """返回空列表的 data_fetcher。"""
    return []


# ═══════════════════════════════════════════════════════════════════
#  1. Put + Get 回环
# ═══════════════════════════════════════════════════════════════════


class TestPutGetRoundtrip:
    """put 后 get 回环测试。"""

    def test_put_then_get_same_range(self, tmp_cache_dir):
        """写入数据后，查询相同范围应得到相同数据。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-03-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        assert len(result) > 0
        # 验证日期范围
        assert result["date"].min() >= "2024-01-02"
        assert result["date"].max() <= "2024-03-31"

    def test_put_then_get_subset_range(self, tmp_cache_dir):
        """写入大范围数据后，查询子范围应返回正确的子集。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-12-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-06-01", end_date="2024-06-30",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        assert all(result["date"] >= "2024-06-01")
        assert all(result["date"] <= "2024-06-30")

    def test_put_single_day(self, tmp_cache_dir):
        """写入一天数据后能读回。"""
        engine = _make_engine(tmp_cache_dir)
        df = pd.DataFrame([{
            "date": "2024-06-15", "code": "000001",
            "open": 10.0, "high": 10.5, "low": 9.5,
            "close": 10.2, "volume": 1000.0, "amount": 100000.0,
        }])

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-06-15", end_date="2024-06-15",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["date"] == "2024-06-15"

    def test_put_empty_df_no_write(self, tmp_cache_dir):
        """写入空 DataFrame 不应创建文件。"""
        engine = _make_engine(tmp_cache_dir)
        engine.put(
            symbol="000001", period="daily", data=pd.DataFrame(),
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 不应有任何文件被创建
        arrow_files = list(tmp_cache_dir.rglob("*.arrow"))
        assert len(arrow_files) == 0

    def test_put_creates_correct_partition_files(self, tmp_cache_dir):
        """put 应按年份创建正确的分区文件。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2023-06-01", "2024-06-30")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 应创建 2023.arrow 和 2024.arrow
        symbol_dir = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        assert (symbol_dir / "2023.arrow").exists()
        assert (symbol_dir / "2024.arrow").exists()

    def test_put_monthly_partition(self, tmp_cache_dir):
        """monthly 规则应按月创建分区文件。"""
        monthly_rules = [
            PartitionRuleCfg(
                match={"asset_type": "stock", "period": "daily"},
                granularity="monthly",
            ),
        ]
        engine = _make_engine(tmp_cache_dir, rules=monthly_rules)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-03-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        symbol_dir = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        assert (symbol_dir / "2024_01.arrow").exists()
        assert (symbol_dir / "2024_02.arrow").exists()
        assert (symbol_dir / "2024_03.arrow").exists()


# ═══════════════════════════════════════════════════════════════════
#  2. Cache Hit / Miss + data_fetcher
# ═══════════════════════════════════════════════════════════════════


class TestCacheHitMiss:
    """缓存命中/未命中 + 回源测试。"""

    def test_cache_miss_with_fetcher(self, tmp_cache_dir):
        """缓存未命中时调用 data_fetcher 回源。"""
        engine = _make_engine(tmp_cache_dir)
        fetch_called = {"count": 0}

        def fetcher(symbol, period, start, end, adjust):
            fetch_called["count"] += 1
            return make_ohlcv_records(symbol, start, end)

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
            data_fetcher=fetcher,
        )

        assert result is not None
        assert fetch_called["count"] == 1

    def test_cache_miss_without_fetcher_returns_none(self, tmp_cache_dir):
        """缓存未命中且无 data_fetcher 时返回 None。"""
        engine = _make_engine(tmp_cache_dir)

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is None

    def test_cache_hit_no_fetcher_call(self, tmp_cache_dir):
        """缓存命中时不应调用 data_fetcher。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        fetch_called = {"count": 0}

        def fetcher(symbol, period, start, end, adjust):
            fetch_called["count"] += 1
            return make_ohlcv_records(symbol, start, end)

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-06-30",
            asset_type="stock", market="zh_a", adjust="hfq",
            data_fetcher=fetcher,
        )

        assert result is not None
        assert fetch_called["count"] == 0

    def test_cache_miss_fetcher_returns_empty(self, tmp_cache_dir):
        """fetcher 返回空列表时 get 应返回 None。"""
        engine = _make_engine(tmp_cache_dir)

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
            data_fetcher=_empty_fetcher,
        )

        assert result is None

    def test_cache_miss_fetcher_writes_to_cache(self, tmp_cache_dir):
        """cache miss 回源后数据应被写入缓存。"""
        engine = _make_engine(tmp_cache_dir)

        # 第一次查询，触发回源
        result1 = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
            data_fetcher=_simple_fetcher,
        )
        assert result1 is not None

        # 验证缓存文件已创建
        arrow_files = list(tmp_cache_dir.rglob("*.arrow"))
        assert len(arrow_files) > 0

        # 第二次查询，不应调用 fetcher
        fetch_called = {"count": 0}

        def counting_fetcher(symbol, period, start, end, adjust):
            fetch_called["count"] += 1
            return make_ohlcv_records(symbol, start, end)

        result2 = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
            data_fetcher=counting_fetcher,
        )
        assert result2 is not None
        assert fetch_called["count"] == 0

    def test_get_increments_access_count(self, tmp_cache_dir):
        """每次 get 应递增 access_count。"""
        engine = _make_engine(tmp_cache_dir)
        assert engine._access_count == 0

        engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-01", end_date="2024-01-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert engine._access_count == 1

        engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-01", end_date="2024-01-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert engine._access_count == 2


# ═══════════════════════════════════════════════════════════════════
#  3. use_cache=False
# ═══════════════════════════════════════════════════════════════════


class TestUseCacheFlag:
    """use_cache=False 行为测试。"""

    def test_use_cache_false_skips_cache_read(self, tmp_cache_dir):
        """use_cache=False 时即使有缓存数据也应回源。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        fetch_called = {"count": 0}

        def fetcher(symbol, period, start, end, adjust):
            fetch_called["count"] += 1
            return make_ohlcv_records(symbol, start, end)

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-06-30",
            asset_type="stock", market="zh_a", adjust="hfq",
            use_cache=False,
            data_fetcher=fetcher,
        )

        assert result is not None
        assert fetch_called["count"] == 1

    def test_use_cache_false_still_writes_to_cache(self, tmp_cache_dir):
        """use_cache=False 时回源后仍应写入缓存。"""
        engine = _make_engine(tmp_cache_dir)

        engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
            use_cache=False,
            data_fetcher=_simple_fetcher,
        )

        # 验证缓存文件已创建
        arrow_files = list(tmp_cache_dir.rglob("*.arrow"))
        assert len(arrow_files) > 0

    def test_use_cache_false_no_fetcher(self, tmp_cache_dir):
        """use_cache=False 且无 fetcher 时返回 None。"""
        engine = _make_engine(tmp_cache_dir)

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
            use_cache=False,
        )

        assert result is None

    def test_use_cache_false_returns_filtered_data(self, tmp_cache_dir):
        """use_cache=False 时返回的数据应包含 date 过滤。"""
        engine = _make_engine(tmp_cache_dir)

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-02-01", end_date="2024-02-28",
            asset_type="stock", market="zh_a", adjust="hfq",
            use_cache=False,
            data_fetcher=_simple_fetcher,
        )

        assert result is not None
        assert all(result["date"] >= "2024-02-01")
        assert all(result["date"] <= "2024-02-28")


# ═══════════════════════════════════════════════════════════════════
#  4. 日期切片
# ═══════════════════════════════════════════════════════════════════


class TestDateSlicing:
    """日期切片测试。"""

    def test_get_returns_data_within_range(self, tmp_cache_dir):
        """get 返回的数据应严格在 [start_date, end_date] 范围内。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-12-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-06-10", end_date="2024-06-20",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        assert all(result["date"] >= "2024-06-10")
        assert all(result["date"] <= "2024-06-20")

    def test_get_data_sorted_by_date(self, tmp_cache_dir):
        """get 返回的数据应按 date 升序排列。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-12-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-01", end_date="2024-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        dates = result["date"].tolist()
        assert dates == sorted(dates)

    def test_get_range_before_data_returns_none(self, tmp_cache_dir):
        """查询范围在数据之前应返回 None（无 base 文件）。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-06-01", "2024-12-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2023-01-01", end_date="2023-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 2023 没有数据文件，resolve_range 不会返回任何 resolved file
        # has_data 为 False → cache miss → 无 fetcher → None
        assert result is None


# ═══════════════════════════════════════════════════════════════════
#  5. 跨分区查询
# ═══════════════════════════════════════════════════════════════════


class TestCrossPartitionQuery:
    """跨年/跨分区查询测试。"""

    def test_cross_year_query(self, tmp_cache_dir):
        """跨年查询应合并两年的数据。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2023-01-02", "2024-12-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2023-11-01", end_date="2024-02-28",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        assert all(result["date"] >= "2023-11-01")
        assert all(result["date"] <= "2024-02-28")
        # 验证包含两年的数据
        years = set(result["date"].str[:4])
        assert "2023" in years
        assert "2024" in years

    def test_three_year_query(self, tmp_cache_dir):
        """三年跨度的查询。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2022-01-02", "2024-12-31")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2022-06-01", end_date="2024-06-30",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        years = sorted(set(result["date"].str[:4]))
        assert "2022" in years
        assert "2023" in years
        assert "2024" in years

    def test_monthly_cross_month_query(self, tmp_cache_dir):
        """monthly 规则跨月查询。"""
        monthly_rules = [
            PartitionRuleCfg(
                match={"asset_type": "stock", "period": "daily"},
                granularity="monthly",
            ),
        ]
        engine = _make_engine(tmp_cache_dir, rules=monthly_rules)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")

        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-02-15", end_date="2024-04-15",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        assert all(result["date"] >= "2024-02-15")
        assert all(result["date"] <= "2024-04-15")


# ═══════════════════════════════════════════════════════════════════
#  6. 增量写入
# ═══════════════════════════════════════════════════════════════════


class TestIncrementalWrite:
    """增量写入测试。"""

    def test_second_put_writes_incremental(self, tmp_cache_dir):
        """对已有 base 文件再次 put 应写入增量文件。"""
        engine = _make_engine(tmp_cache_dir)

        # 第一次写入
        df1 = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")
        engine.put(
            symbol="000001", period="daily", data=df1,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        symbol_dir = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        base_files = list(symbol_dir.glob("*.arrow"))
        assert any("2024.arrow" == f.name for f in base_files)
        assert not any(".inc." in f.name for f in base_files)

        # 第二次写入（同一年，不同日期范围）
        df2 = make_ohlcv_df("000001", "2024-07-01", "2024-12-31")
        engine.put(
            symbol="000001", period="daily", data=df2,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 应创建增量文件
        inc_files = [f for f in symbol_dir.glob("*.arrow") if ".inc." in f.name]
        assert len(inc_files) >= 1

    def test_read_with_base_and_incremental(self, tmp_cache_dir):
        """读取时应合并 base + 增量文件。"""
        engine = _make_engine(tmp_cache_dir)

        # 写 base
        df1 = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")
        engine.put(
            symbol="000001", period="daily", data=df1,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 写增量
        df2 = make_ohlcv_df("000001", "2024-07-01", "2024-12-31")
        engine.put(
            symbol="000001", period="daily", data=df2,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 读取全年
        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        # 应包含上半年和下半年的数据
        assert result["date"].min() <= "2024-01-05"
        assert result["date"].max() >= "2024-11-01"


# ═══════════════════════════════════════════════════════════════════
#  7. 去重
# ═══════════════════════════════════════════════════════════════════


class TestDeduplication:
    """读取时去重测试。"""

    def test_dedup_keeps_last(self, tmp_cache_dir):
        """重复日期的数据应保留后者（keep last）。"""
        engine = _make_engine(tmp_cache_dir)

        # 第一次写入
        df1 = make_ohlcv_df("000001", "2024-01-02", "2024-01-10", price_base=10.0)
        engine.put(
            symbol="000001", period="daily", data=df1,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 第二次写入（覆盖部分日期，price_base 不同）
        df2 = make_ohlcv_df("000001", "2024-01-05", "2024-01-15", price_base=20.0)
        engine.put(
            symbol="000001", period="daily", data=df2,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-01-15",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        # 检查 2024-01-05 的数据来自第二次写入 (price_base=20.0)
        row_0105 = result[result["date"] == "2024-01-05"]
        assert len(row_0105) == 1
        assert row_0105.iloc[0]["open"] >= 20.0

    def test_no_duplicate_dates_in_result(self, tmp_cache_dir):
        """结果中不应有重复日期。"""
        engine = _make_engine(tmp_cache_dir)

        df1 = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")
        engine.put(
            symbol="000001", period="daily", data=df1,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        df2 = make_ohlcv_df("000001", "2024-04-01", "2024-12-31")
        engine.put(
            symbol="000001", period="daily", data=df2,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        result = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result is not None
        dates = result["date"].tolist()
        assert len(dates) == len(set(dates)), "no duplicate dates expected"


# ═══════════════════════════════════════════════════════════════════
#  8. 不同 symbol 隔离
# ═══════════════════════════════════════════════════════════════════


class TestSymbolIsolation:
    """不同 symbol 之间数据隔离测试。"""

    def test_different_symbols_isolated(self, tmp_cache_dir):
        """不同 symbol 的数据应互相隔离。"""
        engine = _make_engine(tmp_cache_dir)

        df1 = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")
        df2 = make_ohlcv_df("600036", "2024-01-02", "2024-06-30", price_base=50.0)

        engine.put(
            symbol="000001", period="daily", data=df1,
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        engine.put(
            symbol="600036", period="daily", data=df2,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        r1 = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-06-30",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        r2 = engine.get(
            symbol="600036", period="daily",
            start_date="2024-01-02", end_date="2024-06-30",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert r1 is not None
        assert r2 is not None
        # 000001 的 price_base=10.0, 600036 的 price_base=50.0
        assert r1["open"].mean() < 30.0
        assert r2["open"].mean() > 30.0


# ═══════════════════════════════════════════════════════════════════
#  9. 内部方法
# ═══════════════════════════════════════════════════════════════════


class TestInternalMethods:
    """CacheEngine 内部方法测试。"""

    def test_group_by_partition_yearly(self, tmp_cache_dir):
        """yearly 分组应按年分组。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2023-06-01", "2024-06-30")

        groups = engine._group_by_partition(df, "yearly")

        assert len(groups) == 2
        base_names = [name for name, _ in groups]
        assert "2023" in base_names
        assert "2024" in base_names

    def test_group_by_partition_monthly(self, tmp_cache_dir):
        """monthly 分组应按月分组。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-03-31")

        groups = engine._group_by_partition(df, "monthly")

        assert len(groups) == 3
        base_names = [name for name, _ in groups]
        assert "2024_01" in base_names
        assert "2024_02" in base_names
        assert "2024_03" in base_names

    def test_group_by_partition_no_date_column(self, tmp_cache_dir):
        """无 date 列时应返回 ('unknown', df)。"""
        engine = _make_engine(tmp_cache_dir)
        df = pd.DataFrame({"open": [1, 2], "close": [3, 4]})

        groups = engine._group_by_partition(df, "yearly")

        assert len(groups) == 1
        assert groups[0][0] == "unknown"

    def test_extract_year(self, tmp_cache_dir):
        """_extract_year 正确提取年份。"""
        engine = _make_engine(tmp_cache_dir)
        assert engine._extract_year("2024") == 2024
        assert engine._extract_year("2024_06") == 2024

    def test_extract_month(self, tmp_cache_dir):
        """_extract_month 正确提取月份。"""
        engine = _make_engine(tmp_cache_dir)
        assert engine._extract_month("2024") is None
        assert engine._extract_month("2024_01") == 1
        assert engine._extract_month("2024_12") == 12

    def test_get_inc_date(self, tmp_cache_dir):
        """_get_inc_date 从 DataFrame date 列获取日期标识。"""
        engine = _make_engine(tmp_cache_dir)
        df = pd.DataFrame({"date": ["2024-06-15", "2024-06-20"]})
        assert engine._get_inc_date(df) == "20240620"

    def test_get_inc_date_no_date_column(self, tmp_cache_dir):
        """无 date 列时使用今天日期。"""
        engine = _make_engine(tmp_cache_dir)
        df = pd.DataFrame({"open": [1]})
        result = engine._get_inc_date(df)
        assert len(result) == 8  # YYYYMMDD


# ═══════════════════════════════════════════════════════════════════
#  10. 并发读写
# ═══════════════════════════════════════════════════════════════════


class TestConcurrentAccess:
    """并发访问测试。"""

    def test_concurrent_puts_different_symbols(self, tmp_cache_dir):
        """不同 symbol 并发写入不应出错。"""
        engine = _make_engine(tmp_cache_dir)
        errors = []

        def putter(symbol):
            try:
                df = make_ohlcv_df(symbol, "2024-01-02", "2024-06-30")
                engine.put(
                    symbol=symbol, period="daily", data=df,
                    asset_type="stock", market="zh_a", adjust="hfq",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=putter, args=(f"00000{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_reads_same_symbol(self, tmp_cache_dir):
        """并发读取同一 symbol 不应出错。"""
        engine = _make_engine(tmp_cache_dir)
        df = make_ohlcv_df("000001", "2024-01-02", "2024-12-31")
        engine.put(
            symbol="000001", period="daily", data=df,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        results = []
        errors = []

        def reader():
            try:
                r = engine.get(
                    symbol="000001", period="daily",
                    start_date="2024-01-02", end_date="2024-12-31",
                    asset_type="stock", market="zh_a", adjust="hfq",
                )
                if r is not None:
                    results.append(len(r))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10
        # 所有结果应有相同的行数
        assert len(set(results)) == 1

    def test_concurrent_put_and_get(self, tmp_cache_dir):
        """并发 put + get 不应崩溃。"""
        engine = _make_engine(tmp_cache_dir)
        errors = []

        def writer():
            try:
                for i in range(3):
                    df = make_ohlcv_df("000001", "2024-01-02", "2024-12-31")
                    engine.put(
                        symbol="000001", period="daily", data=df,
                        asset_type="stock", market="zh_a", adjust="hfq",
                    )
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(3):
                    engine.get(
                        symbol="000001", period="daily",
                        start_date="2024-01-02", end_date="2024-12-31",
                        asset_type="stock", market="zh_a", adjust="hfq",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ═══════════════════════════════════════════════════════════════════
#  11. Compaction 集成
# ═══════════════════════════════════════════════════════════════════


class TestCompactionIntegration:
    """CacheEngine 与 Compaction 的集成测试。"""

    def test_put_then_compact_then_get(self, tmp_cache_dir):
        """写入增量 → compact → 读取应正常工作。"""
        engine = _make_engine(tmp_cache_dir)

        # 第一次写入 base
        df1 = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")
        engine.put(
            symbol="000001", period="daily", data=df1,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 第二次写入增量
        df2 = make_ohlcv_df("000001", "2024-07-01", "2024-12-31")
        engine.put(
            symbol="000001", period="daily", data=df2,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 执行 compaction
        result = engine.compaction_manager.compact_symbol(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert result.bases_compacted == 1

        # compact 后读取
        data = engine.get(
            symbol="000001", period="daily",
            start_date="2024-01-02", end_date="2024-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert data is not None
        assert len(data) > 0

    def test_compaction_removes_inc_files(self, tmp_cache_dir):
        """compaction 后增量文件应被删除。"""
        engine = _make_engine(tmp_cache_dir)

        df1 = make_ohlcv_df("000001", "2024-01-02", "2024-06-30")
        engine.put(
            symbol="000001", period="daily", data=df1,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        df2 = make_ohlcv_df("000001", "2024-07-01", "2024-12-31")
        engine.put(
            symbol="000001", period="daily", data=df2,
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        symbol_dir = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        inc_before = list(symbol_dir.glob("*.inc.*.arrow"))
        assert len(inc_before) > 0

        engine.compaction_manager.compact_symbol(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        inc_after = list(symbol_dir.glob("*.inc.*.arrow"))
        assert len(inc_after) == 0


# ═══════════════════════════════════════════════════════════════════
#  12. 属性访问
# ═══════════════════════════════════════════════════════════════════


class TestProperties:
    """CacheEngine 属性测试。"""

    def test_compaction_lock_property(self, tmp_cache_dir):
        engine = _make_engine(tmp_cache_dir)
        assert engine.compaction_lock is not None

    def test_compaction_manager_property(self, tmp_cache_dir):
        engine = _make_engine(tmp_cache_dir)
        assert engine.compaction_manager is not None

    def test_resolver_property(self, tmp_cache_dir):
        engine = _make_engine(tmp_cache_dir)
        assert engine.resolver is not None

    def test_storage_property(self, tmp_cache_dir):
        engine = _make_engine(tmp_cache_dir)
        assert engine.storage is not None
        assert engine.storage.cache_dir == tmp_cache_dir

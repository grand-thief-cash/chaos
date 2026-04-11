"""CompactionLock + CompactionManager 单元测试。

覆盖：
- CompactionLock：并发读、读写互斥、超时、Compaction 独占
- CompactionManager：compact_symbol、compact_all、空目录、合并错误
"""

import threading
import time
from pathlib import Path
from typing import List

import pandas as pd
import pytest

from artemis.engines.cache_engine.compaction import (
    CompactionLock,
    CompactionManager,
    CompactionResult,
)
from artemis.engines.cache_engine.storage import ArrowStorage

from tests.conftest import DEFAULT_PARTITION_RULES


def _make_df(rows: int = 5, start_date: str = "2024-01-02", symbol: str = "000001") -> pd.DataFrame:
    from datetime import date, timedelta

    data = []
    start_d = date.fromisoformat(start_date)
    for i in range(rows):
        d = start_d + timedelta(days=i)
        data.append({
            "date": d.isoformat(),
            "code": symbol,
            "open": 10.0 + i,
            "high": 10.5 + i,
            "low": 9.5 + i,
            "close": 10.2 + i,
            "volume": 1000.0 + i,
            "amount": 100000.0 + i,
        })
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════
#  CompactionLock
# ═══════════════════════════════════════════════════════════════════


class TestCompactionLock:
    """CompactionLock 双向互斥测试。"""

    def test_multiple_concurrent_reads_allowed(self):
        """多个读操作可以同时持有锁。"""
        lock = CompactionLock()
        readers_holding = []
        barrier = threading.Barrier(3)

        def reader(idx):
            assert lock.acquire_read(timeout=5)
            readers_holding.append(idx)
            barrier.wait(timeout=5)  # 等所有 reader 都拿到锁
            lock.release_read()

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(readers_holding) == 3
        assert lock.active_reads == 0

    def test_compaction_blocks_reads(self):
        """Compaction 持有锁时，读操作应等待。"""
        lock = CompactionLock()
        assert lock.acquire_compaction(timeout=1)
        read_acquired = threading.Event()
        read_done = threading.Event()

        def reader():
            # 尝试获取读锁，应被阻塞
            if lock.acquire_read(timeout=5):
                read_acquired.set()
                lock.release_read()
                read_done.set()

        t = threading.Thread(target=reader)
        t.start()

        # 给 reader 一点时间尝试获取锁
        time.sleep(0.1)
        assert not read_acquired.is_set(), "read should be blocked during compaction"

        # 释放 compaction
        lock.release_compaction()
        t.join(timeout=5)

        assert read_acquired.is_set()
        assert read_done.is_set()

    def test_reads_block_compaction(self):
        """有活跃读者时，Compaction 应等待。"""
        lock = CompactionLock()
        assert lock.acquire_read(timeout=1)

        compaction_acquired = threading.Event()

        def compactor():
            if lock.acquire_compaction(timeout=5):
                compaction_acquired.set()
                lock.release_compaction()

        t = threading.Thread(target=compactor)
        t.start()

        time.sleep(0.1)
        assert not compaction_acquired.is_set(), "compaction should wait for reads"

        lock.release_read()
        t.join(timeout=5)
        assert compaction_acquired.is_set()

    def test_compaction_is_exclusive(self):
        """同时只能有一个 Compaction。"""
        lock = CompactionLock()
        assert lock.acquire_compaction(timeout=1)

        second_acquired = threading.Event()

        def second_compactor():
            if lock.acquire_compaction(timeout=0.5):
                second_acquired.set()
                lock.release_compaction()

        t = threading.Thread(target=second_compactor)
        t.start()
        t.join(timeout=2)

        assert not second_acquired.is_set(), "second compaction should be blocked"
        lock.release_compaction()

    def test_read_timeout(self):
        """读操作在 Compaction 进行中应超时。"""
        lock = CompactionLock()
        assert lock.acquire_compaction(timeout=1)

        # 读操作应超时
        result = lock.acquire_read(timeout=0.2)
        assert result is False

        lock.release_compaction()

    def test_compaction_timeout(self):
        """Compaction 在有活跃读者时应超时。"""
        lock = CompactionLock()
        assert lock.acquire_read(timeout=1)

        result = lock.acquire_compaction(timeout=0.2)
        assert result is False

        lock.release_read()

    def test_is_compacting_property(self):
        """is_compacting 属性应正确反映状态。"""
        lock = CompactionLock()
        assert not lock.is_compacting

        lock.acquire_compaction(timeout=1)
        assert lock.is_compacting

        lock.release_compaction()
        assert not lock.is_compacting

    def test_active_reads_property(self):
        """active_reads 属性应正确反映活跃读者数。"""
        lock = CompactionLock()
        assert lock.active_reads == 0

        lock.acquire_read(timeout=1)
        lock.acquire_read(timeout=1)
        assert lock.active_reads == 2

        lock.release_read()
        assert lock.active_reads == 1

        lock.release_read()
        assert lock.active_reads == 0

    def test_release_read_notifies_compaction(self):
        """最后一个 reader 释放锁时应通知等待的 compaction。"""
        lock = CompactionLock()
        lock.acquire_read(timeout=1)

        compaction_done = threading.Event()

        def compactor():
            lock.acquire_compaction(timeout=5)
            lock.release_compaction()
            compaction_done.set()

        t = threading.Thread(target=compactor)
        t.start()

        time.sleep(0.1)
        lock.release_read()
        t.join(timeout=3)
        assert compaction_done.is_set()

    def test_release_compaction_notifies_reads(self):
        """compaction 释放锁时应通知等待的 readers。"""
        lock = CompactionLock()
        lock.acquire_compaction(timeout=1)

        read_done = threading.Event()

        def reader():
            lock.acquire_read(timeout=5)
            lock.release_read()
            read_done.set()

        t = threading.Thread(target=reader)
        t.start()

        time.sleep(0.1)
        lock.release_compaction()
        t.join(timeout=3)
        assert read_done.is_set()


# ═══════════════════════════════════════════════════════════════════
#  CompactionManager
# ═══════════════════════════════════════════════════════════════════


class TestCompactionManager:
    """CompactionManager 测试。"""

    def _setup_cache(
        self,
        tmp_cache_dir: Path,
        symbol: str = "000001",
        base_rows: int = 5,
        inc_rows: int = 2,
        inc_count: int = 1,
    ) -> ArrowStorage:
        """创建 base + 增量文件的辅助方法。"""
        from artemis.models.configs import CacheEngineCfg, PartitionRuleCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = ArrowStorage(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)

        dir_path = resolver.resolve_dir(
            symbol=symbol, period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        dir_path.mkdir(parents=True, exist_ok=True)

        # 写 base 文件
        base_path = dir_path / "2024.arrow"
        base_df = _make_df(base_rows, "2024-01-02", symbol)
        storage.write_df(base_path, base_df)

        # 写增量文件
        for i in range(inc_count):
            start_d = f"2024-06-{15 + i:02d}"
            inc_path = dir_path / f"2024.inc.202406{15 + i:02d}.arrow"
            inc_df = _make_df(inc_rows, start_d, symbol)
            storage.write_df(inc_path, inc_df)

        return storage

    def test_compact_symbol_merges_incremental(self, tmp_cache_dir):
        """compact_symbol 应合并增量文件到 base。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = self._setup_cache(tmp_cache_dir, base_rows=5, inc_rows=2, inc_count=1)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        result = manager.compact_symbol(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert isinstance(result, CompactionResult)
        assert result.symbol == "000001"
        assert result.bases_compacted == 1
        assert result.inc_files_merged == 1
        assert result.total_rows == 7  # 5 base + 2 inc
        assert result.duration_ms >= 0

    def test_compact_symbol_no_incremental_files(self, tmp_cache_dir):
        """无增量文件时 bases_compacted 应为 0。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = ArrowStorage(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        # 只有 base，无增量
        dir_path = resolver.resolve_dir(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        dir_path.mkdir(parents=True, exist_ok=True)
        storage.write_df(dir_path / "2024.arrow", _make_df(5))

        result = manager.compact_symbol(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result.bases_compacted == 0
        assert result.inc_files_merged == 0

    def test_compact_symbol_dir_not_exists(self, tmp_cache_dir):
        """symbol 目录不存在时应安全返回。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = ArrowStorage(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        result = manager.compact_symbol(
            symbol="999999", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result.bases_compacted == 0
        assert result.inc_files_merged == 0
        assert result.total_rows == 0

    def test_compact_symbol_multiple_incremental_files(self, tmp_cache_dir):
        """多个增量文件应全部合并。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = self._setup_cache(tmp_cache_dir, base_rows=5, inc_rows=2, inc_count=3)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        result = manager.compact_symbol(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        assert result.bases_compacted == 1
        assert result.inc_files_merged == 3
        # inc files start at 06-15, 06-16, 06-17 with 2 rows each → overlap after dedup
        # dates: 01-02~01-06 (base) + 06-15, 06-16, 06-17, 06-18 (deduped inc) = 9
        assert result.total_rows == 9

    def test_compact_all(self, tmp_cache_dir):
        """compact_all 遍历整个 cache_dir。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = ArrowStorage(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        # 为两个 symbol 创建 base + inc
        for symbol in ["000001", "600036"]:
            dir_path = resolver.resolve_dir(
                symbol=symbol, period="daily",
                asset_type="stock", market="zh_a", adjust="hfq",
            )
            dir_path.mkdir(parents=True, exist_ok=True)
            storage.write_df(dir_path / "2024.arrow", _make_df(5, "2024-01-02", symbol))
            storage.write_df(
                dir_path / "2024.inc.20240615.arrow",
                _make_df(2, "2024-06-15", symbol),
            )

        results = manager.compact_all()
        assert len(results) == 2
        assert all(r.bases_compacted == 1 for r in results)
        assert all(r.inc_files_merged == 1 for r in results)

    def test_compact_all_empty_dir(self, tmp_cache_dir):
        """空 cache_dir 时 compact_all 返回空列表。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = ArrowStorage(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        results = manager.compact_all()
        assert results == []

    def test_compact_all_only_base_no_inc(self, tmp_cache_dir):
        """只有 base 文件无增量时 compact_all 不执行合并。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = ArrowStorage(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        dir_path = resolver.resolve_dir(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        dir_path.mkdir(parents=True, exist_ok=True)
        storage.write_df(dir_path / "2024.arrow", _make_df(5))

        results = manager.compact_all()
        assert results == []

    def test_compact_deduplicates(self, tmp_cache_dir):
        """compaction 应去重（按 date keep last）。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = ArrowStorage(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        dir_path = resolver.resolve_dir(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        dir_path.mkdir(parents=True, exist_ok=True)

        # base 和 inc 有重叠日期
        base_df = _make_df(5, "2024-01-02")  # 01-02 ~ 01-06
        inc_df = _make_df(3, "2024-01-04")   # 01-04 ~ 01-06

        storage.write_df(dir_path / "2024.arrow", base_df)
        storage.write_df(dir_path / "2024.inc.20240615.arrow", inc_df)

        result = manager.compact_symbol(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )

        # 去重后 01-02, 01-03 from base + 01-04, 01-05, 01-06 from inc(keep last) = 5
        assert result.total_rows == 5

        # 验证合并后的文件数据
        merged_table = storage.read_mmap(dir_path / "2024.arrow")
        merged_df = merged_table.to_pandas()
        dates = merged_df["date"].tolist()
        assert dates == sorted(dates), "merged data should be sorted by date"

    def test_compact_result_has_duration(self, tmp_cache_dir):
        """CompactionResult.duration_ms 应大于等于 0。"""
        from artemis.models.configs import CacheEngineCfg
        from artemis.engines.cache_engine.partition import PartitionResolver

        storage = self._setup_cache(tmp_cache_dir)
        cfg = CacheEngineCfg(
            enabled=True,
            cache_dir=str(tmp_cache_dir),
            partition_rules=DEFAULT_PARTITION_RULES,
        )
        resolver = PartitionResolver(cfg)
        lock = CompactionLock()
        manager = CompactionManager(storage, resolver, lock)

        result = manager.compact_symbol(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert result.duration_ms >= 0

"""Compaction 管理 — CompactionLock 双向互斥 + CompactionManager 增量合并。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from artemis.log.logger import get_logger

logger = get_logger("cache_compaction")


@dataclass
class CompactionResult:
    """一次 Compaction 操作的结果。"""
    symbol: str
    period: str
    bases_compacted: int = 0
    inc_files_merged: int = 0
    total_rows: int = 0
    duration_ms: int = 0


class CompactionLock:
    """Compaction 与读操作之间的双向互斥锁。

    不变量:
    - 多个并发读操作允许
    - Compaction 独占（不允许读、不允许其他 Compaction）
    - 读者和 Compaction 互斥
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._active_reads: int = 0
        self._compaction_active: bool = False

    def acquire_read(self, timeout: float = 30.0) -> bool:
        """获取读锁。Compaction 进行中时等待，超时返回 False。"""
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._compaction_active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                if not self._condition.wait(timeout=remaining):
                    return False
            self._active_reads += 1
            return True

    def release_read(self) -> None:
        """释放读锁。无读者时通知等待的 Compaction。"""
        with self._condition:
            self._active_reads -= 1
            if self._active_reads == 0:
                self._condition.notify_all()

    def acquire_compaction(self, timeout: float = 30.0) -> bool:
        """获取独占 Compaction 锁。有活跃读者时等待，超时返回 False。"""
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._active_reads > 0 or self._compaction_active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                if not self._condition.wait(timeout=remaining):
                    return False
            self._compaction_active = True
            return True

    def release_compaction(self) -> None:
        """释放 Compaction 锁，通知等待的读者。"""
        with self._condition:
            self._compaction_active = False
            self._condition.notify_all()

    @property
    def is_compacting(self) -> bool:
        with self._lock:
            return self._compaction_active

    @property
    def active_reads(self) -> int:
        with self._lock:
            return self._active_reads


class CompactionManager:
    """管理缓存增量文件的 Compaction（合并）。"""

    def __init__(self, storage, partition_resolver, compaction_lock: CompactionLock):
        self._storage = storage
        self._resolver = partition_resolver
        self._lock = compaction_lock

    def compact_symbol(
        self,
        *,
        symbol: str,
        period: str,
        asset_type: str,
        market: str,
        adjust: str,
    ) -> CompactionResult:
        """对单个 symbol 的所有增量文件执行 Compaction。

        1. 解析 symbol 目录
        2. 找到所有 base 文件及其 .inc.*.arrow 文件
        3. 对每个有增量的 base 执行合并
        """
        start_time = time.monotonic()
        result = CompactionResult(symbol=symbol, period=period)

        dir_path = self._resolver.resolve_dir(
            symbol=symbol, period=period,
            asset_type=asset_type, market=market, adjust=adjust,
        )
        if not dir_path.exists():
            logger.debug({"event": "compact_symbol_skip", "reason": "dir_not_exists", "dir": str(dir_path)})
            return result

        # 扫描所有 base .arrow 文件
        for base_path in sorted(dir_path.glob("*.arrow")):
            # 跳过增量文件和临时文件
            if ".inc." in base_path.name or ".tmp." in base_path.name:
                continue

            inc_paths = self._storage.scan_incremental_files(base_path)
            if not inc_paths:
                continue

            logger.info({
                "event": "compact_merging",
                "base": str(base_path),
                "inc_count": len(inc_paths),
            })

            try:
                rows = self._storage.merge_files(base_path, inc_paths)
                result.bases_compacted += 1
                result.inc_files_merged += len(inc_paths)
                result.total_rows += rows
            except Exception as e:
                logger.error({
                    "event": "compact_merge_failed",
                    "base": str(base_path),
                    "error": str(e),
                }, exc_info=True)

        result.duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info({
            "event": "compact_symbol_complete",
            "symbol": symbol,
            "period": period,
            "bases_compacted": result.bases_compacted,
            "inc_files_merged": result.inc_files_merged,
            "duration_ms": result.duration_ms,
        })
        return result

    def compact_all(self) -> List[CompactionResult]:
        """遍历整个 cache_dir，对所有 symbol 执行 Compaction。"""
        results: List[CompactionResult] = []
        cache_dir = self._storage.cache_dir

        if not cache_dir.exists():
            return results

        # 遍历叶子目录中的 base .arrow 文件
        # 目录结构: {asset_type}/{market}/{period}/{adjust}/{symbol}/
        for base_path in sorted(cache_dir.rglob("*.arrow")):
            if ".inc." in base_path.name or ".tmp." in base_path.name:
                continue

            inc_paths = self._storage.scan_incremental_files(base_path)
            if not inc_paths:
                continue

            # 从路径中提取 symbol, period 等
            symbol = base_path.parent.name
            parts = base_path.relative_to(cache_dir).parts
            # parts: [asset_type, market, period, adjust, symbol, filename]
            period = parts[2] if len(parts) > 2 else "daily"

            logger.info({
                "event": "compact_merging",
                "base": str(base_path),
                "inc_count": len(inc_paths),
            })

            try:
                start_time = time.monotonic()
                rows = self._storage.merge_files(base_path, inc_paths)
                r = CompactionResult(
                    symbol=symbol, period=period,
                    bases_compacted=1, inc_files_merged=len(inc_paths),
                    total_rows=rows,
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
                results.append(r)
            except Exception as e:
                logger.error({
                    "event": "compact_merge_failed",
                    "base": str(base_path),
                    "error": str(e),
                }, exc_info=True)

        logger.info({
            "event": "compact_all_complete",
            "total_bases": len(results),
            "total_inc_merged": sum(r.inc_files_merged for r in results),
        })
        return results

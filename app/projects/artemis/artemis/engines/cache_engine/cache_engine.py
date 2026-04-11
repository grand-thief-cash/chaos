"""CacheEngine 核心 — get/put，cache miss 回源，分区分组。"""

from __future__ import annotations

import threading
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from artemis.engines.cache_engine.compaction import CompactionLock, CompactionManager
from artemis.engines.cache_engine.partition import PartitionResolver, ResolvedFile
from artemis.engines.cache_engine.storage import ArrowStorage
from artemis.log.logger import get_logger
from artemis.models.configs import CacheEngineCfg

logger = get_logger("cache_engine")

# 回源函数类型: (symbol, period, start_date, end_date, adjust) -> List[Dict]
DataFetcher = Callable[[str, str, str, str, str], List[Dict[str, Any]]]


class CacheEngine:
    """缓存引擎核心，提供 get/put，cache miss 时自动回源。"""

    def __init__(self, cfg: CacheEngineCfg):
        self._cfg = cfg
        self._resolver = PartitionResolver(cfg)
        self._storage = ArrowStorage(cfg.cache_dir)
        self._compaction_lock = CompactionLock()
        self._compaction_mgr = CompactionManager(
            self._storage, self._resolver, self._compaction_lock,
        )
        self._access_count: int = 0
        self._count_lock = threading.Lock()

        logger.info({"event": "cache_engine_initialized", "cache_dir": cfg.cache_dir})

    @property
    def compaction_lock(self) -> CompactionLock:
        return self._compaction_lock

    @property
    def compaction_manager(self) -> CompactionManager:
        return self._compaction_mgr

    @property
    def resolver(self) -> PartitionResolver:
        return self._resolver

    @property
    def storage(self) -> ArrowStorage:
        return self._storage

    # ── 读取 ──────────────────────────────────────────────────

    def get(
        self,
        *,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        asset_type: str,
        market: str,
        adjust: str,
        use_cache: bool = True,
        data_fetcher: Optional[DataFetcher] = None,
    ) -> Optional[pd.DataFrame]:
        """读取缓存数据，cache miss 时回源。

        Flow:
        1. use_cache=True 时，resolve 文件并尝试读取
        2. 如果有缺失分区且 data_fetcher 可用，回源拉取缺失范围，写入缓存
        3. use_cache=False 时跳过缓存读取，但回源后仍写入缓存
        4. 返回合并后的 DataFrame
        """

        self._increment_access()

        if use_cache:
            resolved = self._resolver.resolve_range(
                symbol=symbol, period=period,
                start_date=start_date, end_date=end_date,
                asset_type=asset_type, market=market, adjust=adjust,
            )
            # 检查是否有 base 文件存在
            has_data = any(not f.is_delta for f in resolved)
            if has_data:
                df = self._read_resolved(resolved, start_date, end_date)
                if df is not None and not df.empty:
                    logger.debug({
                        "event": "cache_hit",
                        "symbol": symbol, "period": period,
                        "start": start_date, "end": end_date,
                    })
                    return df

        # Cache miss 或 use_cache=False: 回源
        if data_fetcher is None:
            return None

        logger.info({
            "event": "cache_miss",
            "symbol": symbol, "period": period,
            "start": start_date, "end": end_date,
        })

        bars = data_fetcher(symbol, period, start_date, end_date, adjust)
        if not bars:
            return None

        df = pd.DataFrame(bars)
        self.put(
            symbol=symbol, period=period, data=df,
            asset_type=asset_type, market=market, adjust=adjust,
        )

        # 重新读取以应用时间切片
        if use_cache:
            return df

        # use_cache=False 时直接返回回源数据，但仍做了 put
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        return df.loc[mask].reset_index(drop=True)

    # ── 写入 ──────────────────────────────────────────────────

    def put(
        self,
        *,
        symbol: str,
        period: str,
        data: pd.DataFrame,
        asset_type: str,
        market: str,
        adjust: str,
    ) -> None:
        """将数据写入缓存，按分区分组。"""
        if data.empty:
            return

        rule = self._resolver.resolve_rule(asset_type, market, period, adjust)
        groups = self._group_by_partition(data, rule.granularity)

        for base_name, partition_df in groups:
            base_path = self._resolver.resolve_base_path(
                symbol=symbol, period=period,
                asset_type=asset_type, market=market, adjust=adjust,
                year=self._extract_year(base_name),
                month=self._extract_month(base_name),
            )

            if self._storage.file_exists(base_path):
                # 写入增量文件: {base_name}.inc.{YYYYMMDD}.arrow
                inc_date = self._get_inc_date(partition_df)
                inc_path = self._resolver.resolve_incremental_path(base_path, inc_date)
                self._storage.write_incremental_df(inc_path, partition_df)
                logger.debug({
                    "event": "cache_write_incremental",
                    "path": str(inc_path), "rows": len(partition_df),
                })
            else:
                # 首次写入 base
                self._storage.write_df(base_path, partition_df)
                logger.debug({
                    "event": "cache_write_base",
                    "path": str(base_path), "rows": len(partition_df),
                })

    # ── 内部方法 ──────────────────────────────────────────────

    def _read_resolved(
        self,
        resolved: List[ResolvedFile],
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """读取并合并 resolved 文件，应用时间切片。"""
        if not self._compaction_lock.acquire_read(timeout=10):
            logger.warning({"event": "cache_read_lock_timeout"})
            return None

        try:
            dfs: List[pd.DataFrame] = []
            for f in resolved:
                table = self._storage.read_mmap(f.path)
                if table is not None:
                    dfs.append(table.to_pandas())

            if not dfs:
                return None

            merged = pd.concat(dfs, ignore_index=True)
            # 去重 + 排序
            if "date" in merged.columns:
                merged = merged.drop_duplicates(subset=["date"], keep="last")
                merged = merged.sort_values(by="date").reset_index(drop=True)
                # 时间切片
                mask = (merged["date"] >= start_date) & (merged["date"] <= end_date)
                merged = merged.loc[mask].reset_index(drop=True)

            return merged if not merged.empty else None
        finally:
            self._compaction_lock.release_read()

    def _group_by_partition(
        self,
        df: pd.DataFrame,
        granularity: str,
    ) -> List[Tuple[str, pd.DataFrame]]:
        """按分区粒度将 DataFrame 分组。

        yearly: 按 date 列的年份分组，base_name = "2025"
        monthly: 按 date 列的年+月分组，base_name = "2025_01"
        """
        if "date" not in df.columns:
            return [("unknown", df)]

        # 尝试解析日期（date 列可能是 string 或 datetime）
        dates = pd.to_datetime(df["date"])

        groups: List[Tuple[str, pd.DataFrame]] = []

        if granularity == "monthly":
            for (year, month), group_df in df.groupby([dates.dt.year, dates.dt.month]):
                base_name = f"{year}_{month:02d}"
                groups.append((base_name, group_df.reset_index(drop=True)))
        else:
            for year, group_df in df.groupby(dates.dt.year):
                groups.append((str(year), group_df.reset_index(drop=True)))

        return groups

    def _get_inc_date(self, df: pd.DataFrame) -> str:
        """从 DataFrame 的 date 列获取增量文件日期标识（YYYYMMDD）。"""
        if "date" in df.columns:
            max_date = pd.to_datetime(df["date"].max())
            return max_date.strftime("%Y%m%d")
        return date.today().strftime("%Y%m%d")

    def _extract_year(self, base_name: str) -> int:
        """从 base_name 提取年份。'2025' → 2025, '2025_01' → 2025"""
        return int(base_name.split("_")[0])

    def _extract_month(self, base_name: str) -> Optional[int]:
        """从 base_name 提取月份。'2025_01' → 1, '2025' → None"""
        parts = base_name.split("_")
        if len(parts) == 2:
            return int(parts[1])
        return None

    def _increment_access(self) -> None:
        """递增访问计数。"""
        with self._count_lock:
            self._access_count += 1

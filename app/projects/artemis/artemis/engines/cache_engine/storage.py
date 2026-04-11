"""Arrow 文件读写存储层 — mmap 零拷贝读取、原子写入、增量合并。"""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Optional

import pyarrow as pa
import pyarrow.ipc as ipc

from artemis.log.logger import get_logger

logger = get_logger("cache_storage")

# OHLCV Arrow schema，匹配 PhoenixA 返回的数据结构
OHLCV_SCHEMA = pa.schema([
    pa.field("date", pa.string()),
    pa.field("code", pa.string()),
    pa.field("open", pa.float64()),
    pa.field("high", pa.float64()),
    pa.field("low", pa.float64()),
    pa.field("close", pa.float64()),
    pa.field("volume", pa.float64()),
    pa.field("amount", pa.float64()),
])


class FileLockManager:
    """Per-file lock manager，保证同文件的并发操作线程安全。"""

    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def get(self, path: Path) -> threading.Lock:
        """获取（或创建）指定文件路径的 Lock。"""
        key = str(path)
        lock = self._locks.get(key)
        if lock is not None:
            return lock
        with self._meta_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock


class ArrowStorage:
    """Arrow IPC 文件读写，支持 mmap 零拷贝读取和原子写入。"""

    def __init__(self, cache_dir: str | Path):
        self._cache_dir = Path(cache_dir)
        self._lock_mgr = FileLockManager()

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    # ── 目录操作 ──────────────────────────────────────────────

    def ensure_dir(self, path: Path) -> None:
        """确保文件所在目录存在。"""
        path.parent.mkdir(parents=True, exist_ok=True)

    # ── 读取 ──────────────────────────────────────────────────

    def read_mmap(self, path: Path) -> Optional[pa.Table]:
        """使用 mmap 读取 Arrow IPC 文件。文件不存在返回 None。"""
        if not path.exists():
            return None
        file_lock = self._lock_mgr.get(path)
        with file_lock:
            try:
                source = pa.memory_map(str(path), 'r')
                reader = ipc.open_file(source)
                return reader.read_all()
            except Exception as e:
                logger.warning({"event": "arrow_read_mmap_failed", "path": str(path), "error": str(e)})
                return None

    def read_to_df(self, path: Path) -> Optional[pa.Table]:
        """读取 Arrow 文件，返回原始 Table（调用者转 DataFrame）。"""
        return self.read_mmap(path)

    # ── 写入 ──────────────────────────────────────────────────

    def write(self, path: Path, table: pa.Table) -> None:
        """将 Arrow Table 写为 IPC 文件，原子写入。线程安全。"""
        self.ensure_dir(path)
        file_lock = self._lock_mgr.get(path)
        with file_lock:
            self._atomic_write(path, table)
            logger.debug({"event": "arrow_write", "path": str(path), "rows": table.num_rows})

    def write_df(self, path: Path, df) -> None:
        """将 pandas DataFrame 写为 Arrow IPC 文件。"""
        table = self._df_to_table(df)
        self.write(path, table)

    def write_incremental(self, path: Path, table: pa.Table) -> None:
        """写入增量文件（与 write 相同逻辑，语义区分）。"""
        self.write(path, table)

    def write_incremental_df(self, path: Path, df) -> None:
        """写入增量文件（DataFrame 版本）。"""
        self.write_df(path, df)

    # ── 合并 ──────────────────────────────────────────────────

    def merge_files(
        self,
        base_path: Path,
        inc_paths: List[Path],
        dedup_column: str = "date",
    ) -> int:
        """合并 base + 所有增量文件为新的 base。

        1. 读取 base table
        2. 读取所有增量 table
        3. concat + 按 dedup_column 去重（keep last）+ 排序
        4. 原子写入新 base
        5. 删除增量文件

        返回合并后的行数。
        """
        file_lock = self._lock_mgr.get(base_path)
        with file_lock:
            tables: List[pa.Table] = []

            # 读取 base
            base_table = self._read_raw(base_path)
            if base_table is not None:
                tables.append(base_table)

            # 读取增量
            for inc_path in inc_paths:
                inc_table = self._read_raw(inc_path)
                if inc_table is not None:
                    tables.append(inc_table)

            if not tables:
                return 0

            # concat
            if len(tables) == 1:
                merged = tables[0]
            else:
                merged = pa.concat_tables(tables)

            # 去重 + 排序（转为 pandas 操作，Arrow 原生去重不方便）
            merged_df = merged.to_pandas()
            merged_df = merged_df.drop_duplicates(subset=[dedup_column], keep="last")
            merged_df = merged_df.sort_values(by=dedup_column).reset_index(drop=True)

            merged_table = self._df_to_table(merged_df)

            # 原子写入
            self._atomic_write(base_path, merged_table)

            # 删除增量文件
            for inc_path in inc_paths:
                self._delete_file_safe(inc_path)

            logger.info({
                "event": "arrow_merge_complete",
                "base": str(base_path),
                "inc_count": len(inc_paths),
                "rows": merged_table.num_rows,
            })
            return merged_table.num_rows

    # ── 文件操作 ──────────────────────────────────────────────

    def file_exists(self, path: Path) -> bool:
        return path.exists()

    def delete_file(self, path: Path) -> None:
        """删除单个 Arrow 文件。"""
        self._delete_file_safe(path)

    def delete_files(self, paths: List[Path]) -> None:
        """删除多个 Arrow 文件。"""
        for p in paths:
            self._delete_file_safe(p)

    def scan_incremental_files(self, base_path: Path) -> List[Path]:
        """扫描 base 文件关联的所有增量文件。
        例如 2025.arrow → 2025.inc.*.arrow
        """
        stem = base_path.stem
        pattern = f"{stem}.inc.*.arrow"
        parent = base_path.parent
        if not parent.exists():
            return []
        return sorted(parent.glob(pattern))

    # ── 内部方法 ──────────────────────────────────────────────

    def _atomic_write(self, path: Path, table: pa.Table) -> None:
        """原子写入：先写 .tmp 再 rename。"""
        tmp_path = path.with_suffix(".tmp.arrow")
        try:
            with ipc.new_file(str(tmp_path), table.schema) as writer:
                writer.write_table(table)
            os.replace(str(tmp_path), str(path))
        except Exception:
            # 清理 tmp 文件
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def _read_raw(self, path: Path) -> Optional[pa.Table]:
        """不带锁的原始读取（调用方需自行加锁）。"""
        if not path.exists():
            return None
        try:
            source = pa.memory_map(str(path), 'r')
            reader = ipc.open_file(source)
            return reader.read_all()
        except Exception as e:
            logger.warning({"event": "arrow_read_raw_failed", "path": str(path), "error": str(e)})
            return None

    def _delete_file_safe(self, path: Path) -> None:
        """安全删除文件，忽略 FileNotFoundError。"""
        try:
            path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning({"event": "arrow_delete_failed", "path": str(path), "error": str(e)})

    def _df_to_table(self, df) -> pa.Table:
        """将 pandas DataFrame 转为 Arrow Table，强制统一为 OHLCV_SCHEMA。"""
        # 只保留 schema 中定义的列
        target_cols = [f.name for f in OHLCV_SCHEMA]
        keep_cols = [c for c in target_cols if c in df.columns]
        df = df[keep_cols]

        # 按目标 schema 中的类型强制转换
        schema_fields = {f.name: f.type for f in OHLCV_SCHEMA}
        for col in keep_cols:
            target_type = schema_fields[col]
            if col in df.columns:
                df[col] = df[col].astype(target_type.to_pandas_dtype())

        table = pa.Table.from_pandas(df, preserve_index=False)
        # 移除 pandas metadata
        return table.replace_schema_metadata({})

"""ArrowStorage 单元测试。

覆盖：读写回环、原子写入、增量文件扫描、合并去重、FileLockManager、边界条件。
"""

import threading
from pathlib import Path
from typing import List

import pandas as pd
import pyarrow as pa
import pytest

from artemis.engines.cache_engine.storage import ArrowStorage, FileLockManager, OHLCV_SCHEMA


# ═══════════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════════


def _make_table(rows: int = 5, start_date: str = "2024-01-02") -> pa.Table:
    """生成一个小的测试 Arrow Table。"""
    from datetime import date, timedelta

    data = []
    start_d = date.fromisoformat(start_date)
    for i in range(rows):
        d = start_d + timedelta(days=i)
        data.append({
            "date": d.isoformat(),
            "code": "000001",
            "open": 10.0 + i,
            "high": 10.5 + i,
            "low": 9.5 + i,
            "close": 10.2 + i,
            "volume": 1000.0 + i,
            "amount": 100000.0 + i,
        })
    df = pd.DataFrame(data)
    return pa.Table.from_pandas(df, preserve_index=False).replace_schema_metadata({})


def _make_df(rows: int = 5, start_date: str = "2024-01-02", symbol: str = "000001") -> pd.DataFrame:
    """生成一个小的测试 DataFrame。"""
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
#  FileLockManager
# ═══════════════════════════════════════════════════════════════════


class TestFileLockManager:
    """FileLockManager 测试。"""

    def test_same_path_returns_same_lock(self):
        """同一路径应返回同一个 Lock 对象。"""
        mgr = FileLockManager()
        path = Path("/tmp/test.arrow")
        lock1 = mgr.get(path)
        lock2 = mgr.get(path)
        assert lock1 is lock2

    def test_different_paths_return_different_locks(self):
        """不同路径应返回不同的 Lock 对象。"""
        mgr = FileLockManager()
        lock1 = mgr.get(Path("/tmp/a.arrow"))
        lock2 = mgr.get(Path("/tmp/b.arrow"))
        assert lock1 is not lock2

    def test_concurrent_access(self):
        """多线程并发获取同一 lock 不应出错。"""
        mgr = FileLockManager()
        path = Path("/tmp/test.arrow")
        results = []
        errors = []

        def worker():
            try:
                lock = mgr.get(path)
                with lock:
                    results.append(threading.current_thread().name)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10


# ═══════════════════════════════════════════════════════════════════
#  ArrowStorage — 写入与读取
# ═══════════════════════════════════════════════════════════════════


class TestArrowStorageReadWrite:
    """ArrowStorage write / read 回环测试。"""

    def test_write_and_read_table(self, tmp_cache_dir):
        """写入 pa.Table 后用 read_mmap 读回，数据一致。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"
        table = _make_table(10)

        storage.write(path, table)
        assert path.exists()

        result = storage.read_mmap(path)
        assert result is not None
        assert result.num_rows == 10
        assert result.column("date")[0].as_py() == "2024-01-02"

    def test_write_df_and_read(self, tmp_cache_dir):
        """写入 DataFrame 后读回，数据一致。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test_df.arrow"
        df = _make_df(5)

        storage.write_df(path, df)
        result = storage.read_mmap(path)
        assert result is not None
        assert result.num_rows == 5

    def test_read_nonexistent_returns_none(self, tmp_cache_dir):
        """读取不存在的文件返回 None。"""
        storage = ArrowStorage(tmp_cache_dir)
        result = storage.read_mmap(tmp_cache_dir / "nonexistent.arrow")
        assert result is None

    def test_read_to_df(self, tmp_cache_dir):
        """read_to_df 应委托给 read_mmap。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"
        storage.write(path, _make_table(3))

        result = storage.read_to_df(path)
        assert result is not None
        assert result.num_rows == 3

    def test_write_creates_parent_dirs(self, tmp_cache_dir):
        """write 应自动创建中间目录。"""
        storage = ArrowStorage(tmp_cache_dir)
        deep_path = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001" / "2024.arrow"
        storage.write(deep_path, _make_table(1))

        assert deep_path.exists()
        assert deep_path.parent.is_dir()

    def test_write_overwrite_existing(self, tmp_cache_dir):
        """写入已存在的文件应覆盖。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"

        storage.write(path, _make_table(5))
        storage.write(path, _make_table(10))

        result = storage.read_mmap(path)
        assert result is not None
        assert result.num_rows == 10


# ═══════════════════════════════════════════════════════════════════
#  ArrowStorage — 原子写入
# ═══════════════════════════════════════════════════════════════════


class TestAtomicWrite:
    """原子写入（先写 .tmp 再 rename）测试。"""

    def test_no_tmp_file_after_write(self, tmp_cache_dir):
        """写入完成后不应残留 .tmp 文件。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"
        storage.write(path, _make_table(5))

        tmp_path = path.with_suffix(".tmp.arrow")
        assert not tmp_path.exists()
        assert path.exists()

    def test_corrupt_file_recovery(self, tmp_cache_dir):
        """如果有一个损坏的 .arrow 文件，read_mmap 应返回 None 而不是崩溃。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "corrupt.arrow"
        # 写入垃圾数据
        path.write_bytes(b"not a valid arrow file")

        result = storage.read_mmap(path)
        assert result is None


# ═══════════════════════════════════════════════════════════════════
#  ArrowStorage — 增量文件
# ═══════════════════════════════════════════════════════════════════


class TestIncrementalFiles:
    """增量文件写入与扫描测试。"""

    def test_write_incremental(self, tmp_cache_dir):
        """write_incremental 应写入正常 .arrow 文件。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "2025.inc.20260413.arrow"
        storage.write_incremental(path, _make_table(1))

        assert path.exists()
        result = storage.read_mmap(path)
        assert result is not None
        assert result.num_rows == 1

    def test_write_incremental_df(self, tmp_cache_dir):
        """write_incremental_df 应写入正常 .arrow 文件。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "2025.inc.20260413.arrow"
        storage.write_incremental_df(path, _make_df(3))

        result = storage.read_mmap(path)
        assert result is not None
        assert result.num_rows == 3

    def test_scan_incremental_files(self, tmp_cache_dir):
        """scan_incremental_files 应正确扫描增量文件。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()
        base_path = dir_path / "2025.arrow"

        # 创建增量文件
        storage.write(base_path, _make_table(5))
        inc1 = dir_path / "2025.inc.20260413.arrow"
        inc2 = dir_path / "2025.inc.20260414.arrow"
        storage.write(inc1, _make_table(1))
        storage.write(inc2, _make_table(1))

        result = storage.scan_incremental_files(base_path)
        assert len(result) == 2
        # 应排序返回
        names = [p.name for p in result]
        assert "2025.inc.20260413.arrow" in names
        assert "2025.inc.20260414.arrow" in names

    def test_scan_incremental_no_files(self, tmp_cache_dir):
        """无增量文件时返回空列表。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()
        base_path = dir_path / "2025.arrow"
        storage.write(base_path, _make_table(5))

        result = storage.scan_incremental_files(base_path)
        assert result == []

    def test_scan_incremental_dir_not_exists(self, tmp_cache_dir):
        """目录不存在时返回空列表。"""
        storage = ArrowStorage(tmp_cache_dir)
        base_path = tmp_cache_dir / "nonexistent" / "2025.arrow"
        result = storage.scan_incremental_files(base_path)
        assert result == []

    def test_scan_only_includes_matching_pattern(self, tmp_cache_dir):
        """scan_incremental_files 只返回匹配的增量文件。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()

        # 写入各种文件
        storage.write(dir_path / "2025.arrow", _make_table(1))
        storage.write(dir_path / "2025.inc.20260413.arrow", _make_table(1))
        storage.write(dir_path / "2024.arrow", _make_table(1))
        storage.write(dir_path / "2024.inc.20260413.arrow", _make_table(1))

        base_path = dir_path / "2025.arrow"
        result = storage.scan_incremental_files(base_path)
        # 只有 2025 的增量文件
        assert len(result) == 1
        assert result[0].name == "2025.inc.20260413.arrow"


# ═══════════════════════════════════════════════════════════════════
#  ArrowStorage — 合并
# ═══════════════════════════════════════════════════════════════════


class TestMergeFiles:
    """merge_files 测试。"""

    def test_merge_base_with_one_inc(self, tmp_cache_dir):
        """base + 1 个增量文件合并，数据正确。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()

        base_path = dir_path / "2024.arrow"
        inc_path = dir_path / "2024.inc.20240615.arrow"

        base_df = _make_df(5, "2024-01-02")
        inc_df = _make_df(3, "2024-06-15")

        storage.write_df(base_path, base_df)
        storage.write_df(inc_path, inc_df)

        rows = storage.merge_files(base_path, [inc_path])
        assert rows == 8  # 5 + 3, no overlap

        result = storage.read_mmap(base_path)
        assert result is not None
        assert result.num_rows == 8

        # 增量文件应被删除
        assert not inc_path.exists()

    def test_merge_dedup_by_date(self, tmp_cache_dir):
        """合并时按 date 去重（keep last）。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()

        base_path = dir_path / "2024.arrow"
        inc_path = dir_path / "2024.inc.20240102.arrow"

        # base 和 inc 都有 2024-01-02 的数据
        base_df = _make_df(5, "2024-01-02")  # dates: 01-02 ~ 01-06
        inc_df = _make_df(3, "2024-01-02")   # dates: 01-02 ~ 01-04, overwrite first 3

        storage.write_df(base_path, base_df)
        storage.write_df(inc_path, inc_df)

        rows = storage.merge_files(base_path, [inc_path])
        assert rows == 5  # 去重后只有 5 个不同日期

        result = storage.read_mmap(base_path)
        result_df = result.to_pandas()
        # 验证排序：按 date 升序
        dates = result_df["date"].tolist()
        assert dates == sorted(dates)

        # 验证 2024-01-02 的数据来自增量文件（keep last）
        row_0102 = result_df[result_df["date"] == "2024-01-02"]
        assert len(row_0102) == 1
        # 增量文件中 2024-01-02 的 close = 10.2
        assert row_0102.iloc[0]["close"] == 10.2

    def test_merge_multiple_incs(self, tmp_cache_dir):
        """base + 多个增量文件合并。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()

        base_path = dir_path / "2024.arrow"
        inc1 = dir_path / "2024.inc.20240615.arrow"
        inc2 = dir_path / "2024.inc.20240616.arrow"

        base_df = _make_df(5, "2024-01-02")
        inc1_df = _make_df(2, "2024-06-15")
        inc2_df = _make_df(2, "2024-06-17")

        storage.write_df(base_path, base_df)
        storage.write_df(inc1, inc1_df)
        storage.write_df(inc2, inc2_df)

        rows = storage.merge_files(base_path, [inc1, inc2])
        assert rows == 9  # 5 + 2 + 2

        assert not inc1.exists()
        assert not inc2.exists()

    def test_merge_no_base(self, tmp_cache_dir):
        """base 不存在，只有增量文件时仍能合并。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()

        base_path = dir_path / "2024.arrow"
        inc_path = dir_path / "2024.inc.20240615.arrow"

        storage.write_df(inc_path, _make_df(3, "2024-06-15"))

        rows = storage.merge_files(base_path, [inc_path])
        assert rows == 3
        assert base_path.exists()
        assert not inc_path.exists()

    def test_merge_empty_inc_list(self, tmp_cache_dir):
        """增量列表为空时直接返回 base 的行数。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()

        base_path = dir_path / "2024.arrow"
        storage.write_df(base_path, _make_df(5))

        rows = storage.merge_files(base_path, [])
        assert rows == 5

    def test_merge_no_files_at_all(self, tmp_cache_dir):
        """base 和 inc 都不存在时返回 0。"""
        storage = ArrowStorage(tmp_cache_dir)
        base_path = tmp_cache_dir / "nonexistent.arrow"

        rows = storage.merge_files(base_path, [])
        assert rows == 0

    def test_merge_corrupt_inc_skipped(self, tmp_cache_dir):
        """损坏的增量文件在合并时被跳过（read 返回 None）。"""
        storage = ArrowStorage(tmp_cache_dir)
        dir_path = tmp_cache_dir / "data"
        dir_path.mkdir()

        base_path = dir_path / "2024.arrow"
        inc_path = dir_path / "2024.inc.corrupt.arrow"

        storage.write_df(base_path, _make_df(5))
        # 写入损坏的增量文件
        inc_path.write_bytes(b"corrupt data")

        rows = storage.merge_files(base_path, [inc_path])
        # base 的 5 行仍然保留
        assert rows == 5
        # 损坏的 inc 文件应被删除（即使读取失败）
        assert not inc_path.exists()


# ═══════════════════════════════════════════════════════════════════
#  ArrowStorage — 文件操作
# ═══════════════════════════════════════════════════════════════════


class TestFileOperations:
    """文件操作测试。"""

    def test_file_exists(self, tmp_cache_dir):
        """file_exists 正确判断文件是否存在。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"
        assert not storage.file_exists(path)

        storage.write(path, _make_table(1))
        assert storage.file_exists(path)

    def test_delete_file(self, tmp_cache_dir):
        """delete_file 删除文件。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"
        storage.write(path, _make_table(1))
        assert path.exists()

        storage.delete_file(path)
        assert not path.exists()

    def test_delete_nonexistent_file_no_error(self, tmp_cache_dir):
        """删除不存在的文件不应报错。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "nonexistent.arrow"
        # 不应抛异常
        storage.delete_file(path)

    def test_delete_files(self, tmp_cache_dir):
        """delete_files 批量删除。"""
        storage = ArrowStorage(tmp_cache_dir)
        paths = []
        for i in range(3):
            p = tmp_cache_dir / f"test_{i}.arrow"
            storage.write(p, _make_table(1))
            paths.append(p)

        storage.delete_files(paths)
        for p in paths:
            assert not p.exists()


# ═══════════════════════════════════════════════════════════════════
#  ArrowStorage — _df_to_table schema 强制转换
# ═══════════════════════════════════════════════════════════════════


class TestSchemaConversion:
    """_df_to_table schema 强制转换测试。"""

    def test_extra_columns_stripped(self, tmp_cache_dir):
        """DataFrame 中有额外列时，写入只保留 OHLCV_SCHEMA 中的列。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"

        df = _make_df(3)
        df["extra_col"] = "should_be_removed"

        storage.write_df(path, df)
        result = storage.read_mmap(path)
        assert result is not None
        column_names = result.column_names
        assert "extra_col" not in column_names
        assert "date" in column_names

    def test_string_types_converted(self, tmp_cache_dir):
        """volume/amount 可能是 int 类型，应被转换为 float64。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"

        df = _make_df(3)
        df["volume"] = df["volume"].astype(int)
        df["amount"] = df["amount"].astype(int)

        storage.write_df(path, df)
        result = storage.read_mmap(path)
        assert result is not None
        # 验证 volume 列的类型是 float64
        vol_type = result.schema.field("volume").type
        assert vol_type == pa.float64()

    def test_cache_dir_property(self, tmp_cache_dir):
        """cache_dir 属性返回正确的路径。"""
        storage = ArrowStorage(tmp_cache_dir)
        assert storage.cache_dir == tmp_cache_dir


# ═══════════════════════════════════════════════════════════════════
#  ArrowStorage — 并发写入
# ═══════════════════════════════════════════════════════════════════


class TestConcurrentAccess:
    """并发写入同一文件测试。"""

    def test_concurrent_writes_same_file(self, tmp_cache_dir):
        """多线程并发写入同一文件不应损坏。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "concurrent.arrow"
        errors = []

        def writer(rows):
            try:
                df = _make_df(rows)
                storage.write_df(path, df)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i + 1,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 文件应该存在且可读
        result = storage.read_mmap(path)
        assert result is not None
        assert result.num_rows >= 1

    def test_concurrent_reads_same_file(self, tmp_cache_dir):
        """多线程并发读取同一文件不应出错。"""
        storage = ArrowStorage(tmp_cache_dir)
        path = tmp_cache_dir / "test.arrow"
        storage.write(path, _make_table(10))

        results = []
        errors = []

        def reader():
            try:
                table = storage.read_mmap(path)
                if table is not None:
                    results.append(table.num_rows)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(r == 10 for r in results)

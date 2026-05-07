"""PartitionResolver 单元测试。

覆盖：规则匹配、路径生成、增量路径、范围枚举、边界条件。
"""

import pytest

from artemis.engines.cache_engine.partition import PartitionResolver, ResolvedFile
from artemis.models.configs import PartitionRuleCfg


# ═══════════════════════════════════════════════════════════════════
#  1. resolve_rule — 规则匹配
# ═════════════════════════════════════════════════ 兀═══════════════


class TestResolveRule:
    """PartitionResolver.resolve_rule() 测试。"""

    def test_exact_match_stock_daily(self, cache_cfg):
        """stock + daily 应匹配到 yearly 规则。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "daily", "hfq")
        assert rule.granularity == "yearly"

    def test_exact_match_stock_1min(self, cache_cfg):
        """stock + 1min 应匹配到 monthly 规则。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "1min", "hfq")
        assert rule.granularity == "monthly"

    def test_exact_match_index_daily(self, cache_cfg):
        """index 应匹配到 yearly 规则（index 规则不检查 period）。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("index", "zh_a", "daily", "nf")
        assert rule.granularity == "yearly"

    def test_fallback_rule(self, cache_cfg):
        """未知 period 应匹配兜底规则（yearly）。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "quarterly", "nf")
        assert rule.granularity == "yearly"

    def test_no_rules_raises(self, cache_cfg_no_rules):
        """无规则时应抛出 ValueError。"""
        resolver = PartitionResolver(cache_cfg_no_rules)
        with pytest.raises(ValueError, match="no partition rule matched"):
            resolver.resolve_rule("stock", "zh_a", "daily", "nf")

    def test_match_checks_asset_type(self, cache_cfg):
        """match 中指定 asset_type 时，不匹配的应跳过。"""
        resolver = PartitionResolver(cache_cfg)
        # bond 不在规则中 → 走兜底
        rule = resolver.resolve_rule("bond", "zh_a", "daily", "nf")
        assert rule.granularity == "yearly"

    def test_match_checks_period(self, cache_cfg):
        """match 中指定 period 时，不匹配的应跳过。"""
        resolver = PartitionResolver(cache_cfg)
        # stock + weekly 应该匹配 weekly 规则
        rule = resolver.resolve_rule("stock", "zh_a", "weekly", "hfq")
        assert rule.granularity == "yearly"

    def test_match_checks_market_ignored_when_not_in_match(self, cache_cfg):
        """规则中没有指定 market 字段时，market 参数不影响匹配。"""
        resolver = PartitionResolver(cache_cfg)
        rule1 = resolver.resolve_rule("stock", "zh_a", "daily", "hfq")
        rule2 = resolver.resolve_rule("stock", "us", "daily", "hfq")
        assert rule1.granularity == rule2.granularity == "yearly"

    def test_fallback_only_config(self, cache_cfg_fallback_only):
        """只有兜底规则时，任何参数都能匹配。"""
        resolver = PartitionResolver(cache_cfg_fallback_only)
        rule = resolver.resolve_rule("anything", "any", "whatever", "none")
        assert rule.granularity == "yearly"

    def test_monthly_only_config(self, cache_cfg_monthly_only):
        """只有 monthly 规则时，stock+daily 匹配 monthly。"""
        resolver = PartitionResolver(cache_cfg_monthly_only)
        rule = resolver.resolve_rule("stock", "zh_a", "daily", "hfq")
        assert rule.granularity == "monthly"


# ═══════════════════════════════════════════════════════════════════
#  2. resolve_dir — 目录路径生成
# ═══════════════════════════════════════════════════════════════════


class TestResolveDir:
    """PartitionResolver.resolve_dir() 测试。"""

    def test_yearly_dir_path(self, cache_cfg, tmp_cache_dir):
        """验证目录路径格式：{cache_dir}/{asset_type}/{market}/{period}/{adjust}/{symbol}"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_dir(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        expected = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        assert result == expected

    def test_dir_does_not_need_to_exist(self, cache_cfg):
        """resolve_dir 返回的目录不需要实际存在。"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_dir(
            symbol="999999", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert not result.exists()
        assert "999999" in str(result)


# ═══════════════════════════════════════════════════════════════════
#  3. resolve_base_path — Base 文件路径生成
# ═══════════════════════════════════════════════════════════════════


class TestResolveBasePath:
    """PartitionResolver.resolve_base_path() 测试。"""

    def test_yearly_path(self, cache_cfg, tmp_cache_dir):
        """yearly 规则生成 {year}.arrow。"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_base_path(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
            year=2024,
        )
        assert result.name == "2024.arrow"
        assert str(result).startswith(str(tmp_cache_dir))

    def test_monthly_path(self, cache_cfg, tmp_cache_dir):
        """monthly 规则生成 {year}_{month:02d}.arrow。"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_base_path(
            symbol="000001", period="1min",
            asset_type="stock", market="zh_a", adjust="hfq",
            year=2024, month=3,
        )
        assert result.name == "2024_03.arrow"

    def test_yearly_ignores_month(self, cache_cfg):
        """yearly 规则即使传入 month 也使用 {year}.arrow。"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_base_path(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
            year=2024, month=6,
        )
        assert result.name == "2024.arrow"

    def test_monthly_without_month(self, cache_cfg):
        """monthly 规则不传 month 时使用 {year}.arrow。"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_base_path(
            symbol="000001", period="1min",
            asset_type="stock", market="zh_a", adjust="hfq",
            year=2024,
        )
        # month=None → 走 else 分支
        assert result.name == "2024.arrow"


# ═══════════════════════════════════════════════════════════════════
#  4. resolve_incremental_path — 增量文件路径
# ═══════════════════════════════════════════════════════════════════


class TestResolveIncrementalPath:
    """PartitionResolver.resolve_incremental_path() 测试。"""

    def test_yearly_inc_path(self, cache_cfg):
        """年分区增量文件: {year}.inc.{YYYYMMDD}.arrow"""
        resolver = PartitionResolver(cache_cfg)
        base = resolver.resolve_base_path(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
            year=2025,
        )
        inc = resolver.resolve_incremental_path(base, "20260413")
        assert inc.name == "2025.inc.20260413.arrow"

    def test_monthly_inc_path(self, cache_cfg):
        """月分区增量文件: {year}_{month}.inc.{YYYYMMDD}.arrow"""
        resolver = PartitionResolver(cache_cfg)
        base = resolver.resolve_base_path(
            symbol="000001", period="1min",
            asset_type="stock", market="zh_a", adjust="hfq",
            year=2026, month=4,
        )
        inc = resolver.resolve_incremental_path(base, "20260413")
        assert inc.name == "2026_04.inc.20260413.arrow"

    def test_inc_path_same_directory(self, cache_cfg):
        """增量文件必须与 base 文件在同一目录。"""
        resolver = PartitionResolver(cache_cfg)
        base = resolver.resolve_base_path(
            symbol="000001", period="daily",
            asset_type="stock", market="zh_a", adjust="hfq",
            year=2025,
        )
        inc = resolver.resolve_incremental_path(base, "20260413")
        assert inc.parent == base.parent


# ═══════════════════════════════════════════════════════════════════
#  5. resolve_range — 范围查询
# ═══════════════════════════════════════════════════════════════════


class TestResolveRange:
    """PartitionResolver.resolve_range() 测试。"""

    def test_single_year_no_files(self, cache_cfg):
        """查询单年范围，无文件时返回空列表。"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_range(
            symbol="000001", period="daily",
            start_date="2024-01-01", end_date="2024-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert result == []

    def test_single_year_with_base(self, cache_cfg, tmp_cache_dir):
        """查询单年范围，只有 base 文件。"""
        resolver = PartitionResolver(cache_cfg)
        # 创建 base 文件
        base_path = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001" / "2024.arrow"
        base_path.parent.mkdir(parents=True, exist_ok=True)
        base_path.touch()

        result = resolver.resolve_range(
            symbol="000001", period="daily",
            start_date="2024-01-01", end_date="2024-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert len(result) == 1
        assert result[0].is_delta is False
        assert result[0].base_name == "2024"
        assert result[0].path.name == "2024.arrow"

    def test_cross_year_resolves_two_partitions(self, cache_cfg, tmp_cache_dir):
        """跨年查询应返回两个分区。"""
        resolver = PartitionResolver(cache_cfg)
        dir_path = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "2024.arrow").touch()
        (dir_path / "2025.arrow").touch()

        result = resolver.resolve_range(
            symbol="000001", period="daily",
            start_date="2024-06-15", end_date="2025-06-16",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        base_names = [f.base_name for f in result if not f.is_delta]
        assert "2024" in base_names
        assert "2025" in base_names

    def test_with_incremental_files(self, cache_cfg, tmp_cache_dir):
        """base + 增量文件都应被 resolve。"""
        resolver = PartitionResolver(cache_cfg)
        dir_path = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "2025.arrow").touch()
        (dir_path / "2025.inc.20260413.arrow").touch()
        (dir_path / "2025.inc.20260414.arrow").touch()

        result = resolver.resolve_range(
            symbol="000001", period="daily",
            start_date="2025-01-01", end_date="2025-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        deltas = [f for f in result if f.is_delta]
        bases = [f for f in result if not f.is_delta]
        assert len(bases) == 1
        assert len(deltas) == 2
        assert all(f.base_name == "2025" for f in result)

    def test_monthly_range(self, cache_cfg):
        """stock + 1min (monthly) 查询应返回月分区。"""
        resolver = PartitionResolver(cache_cfg)
        result = resolver.resolve_range(
            symbol="000001", period="1min",
            start_date="2024-01-01", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        # 无文件，但 resolve_range 会检查文件存在性
        # 这里验证文件不存在时返回空列表
        assert result == []

    def test_monthly_range_with_files(self, cache_cfg, tmp_cache_dir):
        """monthly 规则查询范围中有 base 文件时返回。"""
        resolver = PartitionResolver(cache_cfg)
        dir_path = tmp_cache_dir / "stock" / "zh_a" / "1min" / "hfq" / "000001"
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "2024_01.arrow").touch()
        (dir_path / "2024_02.arrow").touch()
        (dir_path / "2024_03.arrow").touch()

        result = resolver.resolve_range(
            symbol="000001", period="1min",
            start_date="2024-01-01", end_date="2024-03-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        names = [f.path.name for f in result]
        assert "2024_01.arrow" in names
        assert "2024_02.arrow" in names
        assert "2024_03.arrow" in names

    def test_monthly_range_with_inc(self, cache_cfg, tmp_cache_dir):
        """monthly 规则增量文件也被 resolve。"""
        resolver = PartitionResolver(cache_cfg)
        dir_path = tmp_cache_dir / "stock" / "zh_a" / "1min" / "hfq" / "000001"
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "2024_01.arrow").touch()
        (dir_path / "2024_01.inc.20240115.arrow").touch()

        result = resolver.resolve_range(
            symbol="000001", period="1min",
            start_date="2024-01-01", end_date="2024-01-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert len(result) == 2
        deltas = [f for f in result if f.is_delta]
        assert len(deltas) == 1
        assert deltas[0].path.name == "2024_01.inc.20240115.arrow"

    def test_same_day_range(self, cache_cfg):
        """start_date == end_date 只返回一个分区。"""
        resolver = PartitionResolver(cache_cfg)
        # 即使无文件，_enumerate_base_partitions 应该只返回一个分区
        rule = resolver.resolve_rule("stock", "zh_a", "daily", "hfq")
        partitions = resolver._enumerate_base_partitions(rule, "2024-06-15", "2024-06-15")
        assert len(partitions) == 1
        assert partitions[0][0] == "2024"

    def test_three_year_span(self, cache_cfg):
        """三年跨度应枚举三个 yearly 分区。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "daily", "hfq")
        partitions = resolver._enumerate_base_partitions(rule, "2022-06-15", "2024-06-16")
        assert len(partitions) == 3
        assert partitions[0][0] == "2022"
        assert partitions[1][0] == "2023"
        assert partitions[2][0] == "2024"

    def test_monthly_three_months(self, cache_cfg):
        """monthly 规则三个月跨度应枚举三个月分区。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "1min", "hfq")
        partitions = resolver._enumerate_base_partitions(rule, "2024-01-15", "2024-03-20")
        assert len(partitions) == 3
        assert partitions[0][0] == "2024_01"
        assert partitions[1][0] == "2024_02"
        assert partitions[2][0] == "2024_03"

    def test_monthly_cross_year(self, cache_cfg):
        """monthly 规则跨年应正确枚举。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "1min", "hfq")
        partitions = resolver._enumerate_base_partitions(rule, "2024-11-15", "2025-02-20")
        assert len(partitions) == 4
        assert partitions[0][0] == "2024_11"
        assert partitions[1][0] == "2024_12"
        assert partitions[2][0] == "2025_01"
        assert partitions[3][0] == "2025_02"

    def test_resolved_file_covers_start_end(self, cache_cfg, tmp_cache_dir):
        """ResolvedFile 的 covers_start / covers_end 应正确。"""
        resolver = PartitionResolver(cache_cfg)
        dir_path = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "2024.arrow").touch()

        result = resolver.resolve_range(
            symbol="000001", period="daily",
            start_date="2024-06-15", end_date="2024-12-31",
            asset_type="stock", market="zh_a", adjust="hfq",
        )
        assert len(result) == 1
        # yearly 分区 covers_start/covers_end 是整年
        assert result[0].covers_start == "2024-01-01"
        assert result[0].covers_end == "2024-12-31"

    def test_monthly_partition_covers(self, cache_cfg):
        """monthly 分区的 covers 应是整月。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "1min", "hfq")
        partitions = resolver._enumerate_base_partitions(rule, "2024-02-01", "2024-02-15")
        assert len(partitions) == 1
        base_name, p_start, p_end = partitions[0]
        assert base_name == "2024_02"
        assert p_start == "2024-02-01"
        assert p_end == "2024-02-29"  # 2024 是闰年

    def test_monthly_february_non_leap(self, cache_cfg):
        """非闰年 2 月只有 28 天。"""
        resolver = PartitionResolver(cache_cfg)
        rule = resolver.resolve_rule("stock", "zh_a", "1min", "hfq")
        partitions = resolver._enumerate_base_partitions(rule, "2025-02-01", "2025-02-15")
        assert len(partitions) == 1
        _, p_start, p_end = partitions[0]
        assert p_end == "2025-02-28"

"""分区解析器 — 根据分区规则匹配、路径生成、范围查询。"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

from artemis.log.logger import get_logger
from artemis.models.configs import CacheEngineCfg, PartitionRuleCfg

logger = get_logger("cache_partition")


@dataclass(frozen=True)
class ResolvedFile:
    """一个解析后的文件（base 或增量）。"""
    path: Path
    base_name: str       # e.g. "2025" or "2026_04"
    is_delta: bool
    covers_start: str    # YYYY-MM-DD
    covers_end: str      # YYYY-MM-DD


class PartitionResolver:
    """匹配分区规则，生成文件路径，按日期范围 resolve 文件列表。"""

    def __init__(self, cfg: CacheEngineCfg):
        self._cache_dir = Path(cfg.cache_dir)
        self._rules = cfg.partition_rules

    # ── 规则匹配 ──────────────────────────────────────────────

    def resolve_rule(
        self,
        asset_type: str,
        market: str,
        period: str,
        adjust: str,
    ) -> PartitionRuleCfg:
        """找到第一条匹配的分区规则。无匹配或无规则时报错。"""
        for rule in self._rules:
            if self._match_rule(rule, asset_type, market, period, adjust):
                return rule
        raise ValueError(
            f"no partition rule matched for asset_type={asset_type}, "
            f"market={market}, period={period}, adjust={adjust}"
        )

    def _match_rule(
        self,
        rule: PartitionRuleCfg,
        asset_type: str,
        market: str,
        period: str,
        adjust: str,
    ) -> bool:
        match = rule.match
        if not match:
            return True  # 空匹配 = 兜底
        if "asset_type" in match and match["asset_type"] != asset_type:
            return False
        if "market" in match and match["market"] != market:
            return False
        if "period" in match and match["period"] != period:
            return False
        if "adjust" in match and match["adjust"] != adjust:
            return False
        return True

    # ── 路径生成 ──────────────────────────────────────────────

    def resolve_dir(
        self,
        *,
        symbol: str,
        period: str,
        asset_type: str,
        market: str,
        adjust: str,
    ) -> Path:
        """返回 symbol 的分区文件所在目录（不包含日期部分）。"""
        return self._cache_dir / asset_type / market / period / adjust / symbol

    def resolve_base_path(
        self,
        *,
        symbol: str,
        period: str,
        asset_type: str,
        market: str,
        adjust: str,
        year: int,
        month: Optional[int] = None,
    ) -> Path:
        """返回指定年/月的 base .arrow 文件路径。"""
        rule = self.resolve_rule(asset_type, market, period, adjust)
        dir_path = self.resolve_dir(
            symbol=symbol, period=period,
            asset_type=asset_type, market=market, adjust=adjust,
        )
        if rule.granularity == "monthly" and month is not None:
            filename = f"{year}_{month:02d}.arrow"
        else:
            filename = f"{year}.arrow"
        return dir_path / filename

    def resolve_incremental_path(self, base_path: Path, inc_date: str) -> Path:
        """返回增量文件路径: {base_name}.inc.{YYYYMMDD}.arrow"""
        stem = base_path.stem  # e.g. "2025" or "2026_04"
        return base_path.with_name(f"{stem}.inc.{inc_date}.arrow")

    # ── 范围查询 ──────────────────────────────────────────────

    def resolve_range(
        self,
        *,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        asset_type: str,
        market: str,
        adjust: str,
    ) -> List[ResolvedFile]:
        """解析日期范围需要的所有文件（base + incremental）。

        1. 找到匹配的分区规则
        2. 枚举覆盖 [start_date, end_date] 的 base 分区
        3. 对每个 base，扫描目录中的 .inc.*.arrow 文件
        4. 返回完整的 ResolvedFile 列表
        """
        rule = self.resolve_rule(asset_type, market, period, adjust)
        partitions = self._enumerate_base_partitions(rule, start_date, end_date)

        result: List[ResolvedFile] = []
        for base_name, p_start, p_end in partitions:
            dir_path = self.resolve_dir(
                symbol=symbol, period=period,
                asset_type=asset_type, market=market, adjust=adjust,
            )
            base_path = dir_path / f"{base_name}.arrow"
            # base 文件
            if base_path.exists():
                result.append(ResolvedFile(
                    path=base_path, base_name=base_name,
                    is_delta=False, covers_start=p_start, covers_end=p_end,
                ))
            # 增量文件: glob {base_name}.inc.*.arrow
            inc_pattern = f"{base_name}.inc.*.arrow"
            for inc_path in sorted(dir_path.glob(inc_pattern)):
                result.append(ResolvedFile(
                    path=inc_path, base_name=base_name,
                    is_delta=True, covers_start=p_start, covers_end=p_end,
                ))

        return result

    def _enumerate_base_partitions(
        self,
        rule: PartitionRuleCfg,
        start_date: str,
        end_date: str,
    ) -> List[Tuple[str, str, str]]:
        """枚举覆盖 [start_date, end_date] 的所有 base 分区。

        返回 [(base_name, partition_start, partition_end), ...]
        yearly: [("2024", "2024-01-01", "2024-12-31"), ...]
        monthly: [("2024_01", "2024-01-01", "2024-01-31"), ...]
        """
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        results: List[Tuple[str, str, str]] = []

        if rule.granularity == "monthly":
            year, month = start.year, start.month
            while True:
                _, last_day = calendar.monthrange(year, month)
                p_start = date(year, month, 1)
                p_end = date(year, month, last_day)
                base_name = f"{year}_{month:02d}"
                results.append((base_name, p_start.isoformat(), p_end.isoformat()))
                if p_end >= end:
                    break
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        else:
            year = start.year
            while True:
                p_start = date(year, 1, 1)
                p_end = date(year, 12, 31)
                base_name = str(year)
                results.append((base_name, p_start.isoformat(), p_end.isoformat()))
                if p_end >= end:
                    break
                year += 1

        return results

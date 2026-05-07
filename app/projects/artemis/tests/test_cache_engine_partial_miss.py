from pathlib import Path

from artemis.engines.cache_engine.cache_engine import CacheEngine
from artemis.models.configs import CacheEngineCfg
from tests.conftest import DEFAULT_PARTITION_RULES, make_ohlcv_df, make_ohlcv_records


def _make_engine(tmp_cache_dir: Path) -> CacheEngine:
    cfg = CacheEngineCfg(
        enabled=True,
        cache_dir=str(tmp_cache_dir),
        partition_rules=DEFAULT_PARTITION_RULES,
    )
    return CacheEngine(cfg)


class TestCacheEnginePartialMiss:
    def test_partial_partition_hit_still_fetches_missing_range(self, tmp_cache_dir):
        engine = _make_engine(tmp_cache_dir)

        # 只预热 2024 分区，模拟跨年查询时的 partial hit。
        engine.put(
            symbol="000001",
            period="daily",
            data=make_ohlcv_df("000001", "2024-01-02", "2024-12-31"),
            asset_type="stock",
            market="zh_a",
            adjust="hfq",
        )

        fetch_called = {"count": 0}

        def fetcher(symbol, period, start, end, adjust):
            fetch_called["count"] += 1
            return make_ohlcv_records(symbol, start, end)

        result = engine.get(
            symbol="000001",
            period="daily",
            start_date="2024-12-01",
            end_date="2025-01-31",
            asset_type="stock",
            market="zh_a",
            adjust="hfq",
            data_fetcher=fetcher,
        )

        assert fetch_called["count"] == 1, "partial hit must trigger backfill instead of returning incomplete cache data"
        assert result is not None
        assert result["date"].min() <= "2024-12-02"
        assert result["date"].max() >= "2025-01-31"

        symbol_dir = tmp_cache_dir / "stock" / "zh_a" / "daily" / "hfq" / "000001"
        assert (symbol_dir / "2025.arrow").exists()


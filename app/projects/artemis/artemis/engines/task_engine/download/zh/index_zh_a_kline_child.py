from artemis.engines.task_engine.download.zh._amazing_data_kline_child import (
    AmazingDataKlineChild,
    amazing_data_bar_available_at,
)


class IndexZhAKlineChild(AmazingDataKlineChild):
    """Download one incremental mainland-index K-line batch."""

    ASSET_TYPE = "index"


__all__ = ["IndexZhAKlineChild", "amazing_data_bar_available_at"]

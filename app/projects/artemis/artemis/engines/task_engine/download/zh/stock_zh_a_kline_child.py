from artemis.engines.task_engine.download.zh._amazing_data_kline_child import (
    AmazingDataKlineChild,
    amazing_data_bar_available_at,
)


class StockZhAKlineChild(AmazingDataKlineChild):
    """Download one incremental A-share stock K-line batch."""

    ASSET_TYPE = "stock"


__all__ = ["StockZhAKlineChild", "amazing_data_bar_available_at"]

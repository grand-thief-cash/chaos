from artemis.consts import TaskCode
from artemis.engines.task_engine.download.zh._amazing_data_kline_parent import (
    AmazingDataKlineParent,
)


class StockZhAKlineParent(AmazingDataKlineParent):
    """Plan registry-native AmazingData K-lines for A-share stocks."""

    ASSET_TYPE = "stock"
    CHILD_TASK_CODE = TaskCode.STOCK_ZH_A_KLINE_CHILD

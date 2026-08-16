from artemis.consts import TaskCode
from artemis.engines.task_engine.download.zh._amazing_data_kline_parent import (
    AmazingDataKlineParent,
)


class IndexZhAKlineParent(AmazingDataKlineParent):
    """Plan registry-native AmazingData K-lines for mainland indexes."""

    ASSET_TYPE = "index"
    CHILD_TASK_CODE = TaskCode.INDEX_ZH_A_KLINE_CHILD

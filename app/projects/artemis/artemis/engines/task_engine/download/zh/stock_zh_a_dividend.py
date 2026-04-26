from artemis.engines.task_engine.download.zh.base_corporate_action import BaseCorporateActionTask


class StockZHADividend(BaseCorporateActionTask):
    """下载沪深A股分红数据（来源：AmazingData InfoData get_dividend）。"""

    ACTION_TYPE = "dividend"
    REPORT_PERIOD_FIELD = "REPORT_PERIOD"
    PROGRESS_FIELD = "DIV_PROGRESS"

    def _sdk_call(self, info_data, code_list, cache_dir):
        return info_data.get_dividend(code_list, local_path=cache_dir, is_local=False)


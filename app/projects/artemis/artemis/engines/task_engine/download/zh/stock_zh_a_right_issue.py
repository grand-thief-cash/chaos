from artemis.engines.task_engine.download.zh.base_corporate_action import BaseCorporateActionTask


class StockZHARightIssue(BaseCorporateActionTask):
    """下载沪深A股配股数据（来源：AmazingData InfoData get_right_issue）。"""

    ACTION_TYPE = "right_issue"
    REPORT_PERIOD_FIELD = "RIGHTSISSUE_YEAR"
    PROGRESS_FIELD = "PROGRESS"

    def _sdk_call(self, info_data, code_list, cache_dir):
        return info_data.get_right_issue(code_list, local_path=cache_dir, is_local=False)


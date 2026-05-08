from artemis.engines.task_engine.download.zh.base_corporate_action import BaseCorporateActionTask


class StockZHADividend(BaseCorporateActionTask):
    """下载沪深A股分红数据（来源：AmazingData InfoData get_dividend）。

    支持增量下载参数（ctx.params）：
      - symbols: list[str]  — 指定证券代码
      - begin_date: int / end_date: int — 公告日期范围
    """

    ACTION_TYPE = "dividend"
    REPORT_PERIOD_FIELD = "REPORT_PERIOD"
    PROGRESS_FIELD = "DIV_PROGRESS"

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_dividend(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)


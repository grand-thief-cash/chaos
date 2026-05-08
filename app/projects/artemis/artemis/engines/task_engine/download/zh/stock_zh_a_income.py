from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask


class StockZHAIncome(BaseFinancialStatementTask):
    """下载沪深A股利润表数据（来源：AmazingData InfoData get_income）。

    支持增量下载参数（ctx.params）：
      - symbols: list[str]  — 指定证券代码
      - begin_date: int / end_date: int — 报告期范围
    """

    STATEMENT_TYPE = "income"
    SDK_METHOD_NAME = "get_income"

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_income(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)

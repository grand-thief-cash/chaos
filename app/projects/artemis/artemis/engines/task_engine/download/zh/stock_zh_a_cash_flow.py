from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask


class StockZHACashFlow(BaseFinancialStatementTask):
    """下载沪深A股现金流量表数据（来源：AmazingData InfoData get_cash_flow）。

    支持增量下载参数（ctx.params）：
      - symbols: list[str]  — 指定证券代码
      - begin_date: int / end_date: int — 报告期范围
    """

    STATEMENT_TYPE = "cashflow"
    SDK_METHOD_NAME = "get_cash_flow"

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_cash_flow(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)

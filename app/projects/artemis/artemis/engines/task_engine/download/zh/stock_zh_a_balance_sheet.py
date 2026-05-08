from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask


class StockZHABalanceSheet(BaseFinancialStatementTask):
    """下载沪深A股资产负债表数据（来源：AmazingData InfoData get_balance_sheet）。

    支持增量下载参数（ctx.params）：
      - symbols: list[str]  — 指定证券代码（如 ['000001', '600519'] 或 ['000001.SZ']）
      - begin_date: int      — 报告期起始（如 20240101）
      - end_date: int        — 报告期结束
    """

    STATEMENT_TYPE = "balance_sheet"
    SDK_METHOD_NAME = "get_balance_sheet"

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_balance_sheet(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)

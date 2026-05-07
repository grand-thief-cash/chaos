from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask


class StockZHACashFlow(BaseFinancialStatementTask):
    """下载沪深A股现金流量表数据（来源：AmazingData InfoData get_cash_flow）。"""

    STATEMENT_TYPE = "cashflow"
    SDK_METHOD_NAME = "get_cash_flow"

    def _sdk_call(self, info_data, code_list, cache_dir):
        return info_data.get_cash_flow(code_list, local_path=cache_dir, is_local=False)

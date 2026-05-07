from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask


class StockZHAIncome(BaseFinancialStatementTask):
    """下载沪深A股利润表数据（来源：AmazingData InfoData get_income）。"""

    STATEMENT_TYPE = "income"
    SDK_METHOD_NAME = "get_income"

    def _sdk_call(self, info_data, code_list, cache_dir):
        return info_data.get_income(code_list, local_path=cache_dir, is_local=False)

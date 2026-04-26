import pandas as pd

from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask


class StockZHAProfitNotice(BaseFinancialStatementTask):
    """下载沪深A股业绩预告数据（来源：AmazingData InfoData get_profit_notice）。"""

    STATEMENT_TYPE = "profit_notice"
    SDK_METHOD_NAME = "get_profit_notice"

    def _sdk_call(self, info_data, code_list, cache_dir):
        return info_data.get_profit_notice(code_list, local_path=cache_dir, is_local=False)

    def _get_metadata_overrides(self, row):
        # profit_notice has REPORT_TYPE and SECURITY_NAME, but no STATEMENT_TYPE, ACTUAL_ANN_DATE, COMP_TYPE_CODE
        return {
            'report_type': str(row.get('REPORT_TYPE', '')),
            'statement_code': '',
            'security_name': str(row.get('SECURITY_NAME', '')),
            'ann_date': str(row.get('ANN_DATE', '')),
            'actual_ann_date': '',
            'comp_type_code': 0,
        }


import pandas as pd

from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask
from artemis.engines.task_engine.download.zh.utils import normalize_date_yyyymmdd


class StockZHAProfitExpress(BaseFinancialStatementTask):
    """下载沪深A股业绩快报数据（来源：AmazingData InfoData get_profit_express）。"""

    STATEMENT_TYPE = "profit_express"
    SDK_METHOD_NAME = "get_profit_express"

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_profit_express(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)

    def _get_metadata_overrides(self, row):
        def _str(val):
            return '' if pd.isna(val) else str(val).strip()

        # profit_express lacks REPORT_TYPE, SECURITY_NAME, STATEMENT_TYPE, COMP_TYPE_CODE
        return {
            'report_type': '',
            'statement_code': '',
            'security_name': '',
            'ann_date': normalize_date_yyyymmdd(_str(row.get('ANN_DATE'))),
            'actual_ann_date': normalize_date_yyyymmdd(_str(row.get('ACTUAL_ANN_DATE'))),
            'comp_type_code': 0,
        }


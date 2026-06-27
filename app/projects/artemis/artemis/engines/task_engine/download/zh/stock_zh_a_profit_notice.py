import pandas as pd

from artemis.engines.task_engine.download.zh.base_financial_statement import BaseFinancialStatementTask
from artemis.engines.task_engine.download.zh.utils import normalize_date_yyyymmdd


class StockZHAProfitNotice(BaseFinancialStatementTask):
    """下载沪深A股业绩预告数据（来源：AmazingData InfoData get_profit_notice）。"""

    STATEMENT_TYPE = "profit_notice"
    SDK_METHOD_NAME = "get_profit_notice"

    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        return info_data.get_profit_notice(code_list, local_path=cache_dir, is_local=False, **sdk_date_kwargs)

    def _get_metadata_overrides(self, row):
        def _str(val):
            return '' if pd.isna(val) else str(val).strip()

        # profit_notice has REPORT_TYPE and SECURITY_NAME, but no STATEMENT_TYPE, ACTUAL_ANN_DATE, COMP_TYPE_CODE
        return {
            'report_type': _str(row.get('REPORT_TYPE')),
            'statement_code': '',
            'security_name': _str(row.get('SECURITY_NAME')),
            'ann_date': normalize_date_yyyymmdd(_str(row.get('ANN_DATE'))),
            'actual_ann_date': '',
            'comp_type_code': 0,
        }


"""
Base class for financial statement download tasks.

Eliminates duplication across balance_sheet, cashflow, income, profit_express, profit_notice tasks.
Subclasses only need to define:
  - STATEMENT_TYPE: str
  - SDK_METHOD_NAME: str
  - _sdk_call(info_data, code_list, cache_dir) -> result
  - (optional) _get_metadata_overrides(row) -> dict  for tasks with missing fields
  - (optional) _normalize_result(result) -> iterable of DataFrames
"""
import json
import os
from abc import abstractmethod
from typing import Any, Dict, List, Iterable

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


# Fields extracted as structured DB columns; everything else goes into data_json.
METADATA_FIELDS = frozenset({
    'MARKET_CODE', 'SECURITY_NAME', 'STATEMENT_TYPE', 'REPORT_TYPE',
    'REPORTING_PERIOD', 'ANN_DATE', 'ACTUAL_ANN_DATE', 'COMP_TYPE_CODE',
})


class BaseFinancialStatementTask(WorkerUnit):
    """Base for all financial statement download tasks."""

    # Subclasses MUST set these
    STATEMENT_TYPE: str = ""
    SDK_METHOD_NAME: str = ""

    def before_execute(self, ctx: TaskContext) -> None:
        from artemis.core.sdk.manager import sdk_mgr
        from artemis.consts import SDK_NAME

        try:
            sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
        except Exception as e:
            ctx.fail(f"failed to acquire AmazingData SDK: {e}", phase='before_execute')
            return

        self._info_data = ad.InfoData()
        self._base_data = ad.BaseData()

    def execute(self, ctx):
        from artemis.core.config_manager import cfg_mgr

        task_engine_cfg = cfg_mgr.task_engine_config()
        cache_dir = os.path.abspath(task_engine_cfg.amazing_data_cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        try:
            calendar = self._base_data.get_calendar()
            today = calendar[-1]
            all_code_list = self._base_data.get_hist_code_list(
                security_type='EXTRA_STOCK_A_SH_SZ',
                start_date=20130101,
                end_date=today,
            )
            return self._sdk_call(self._info_data, all_code_list, cache_dir)
        except Exception as e:
            ctx.fail(f"fetch {self.STATEMENT_TYPE} failed: {e}", phase='execute')
            return None

    @abstractmethod
    def _sdk_call(self, info_data, code_list, cache_dir):
        """Call the specific SDK method. Override in subclass."""
        raise NotImplementedError

    def _normalize_result(self, result) -> Iterable[pd.DataFrame]:
        """Convert SDK result into an iterable of DataFrames.
        - dict of DataFrames (balance_sheet, cashflow, income): iterate values
        - single DataFrame (profit_express, profit_notice): wrap in list
        """
        if isinstance(result, dict):
            return result.values()
        elif isinstance(result, pd.DataFrame):
            return [result]
        else:
            return []

    def _get_metadata_overrides(self, row) -> Dict[str, Any]:
        """Override for tasks where some metadata fields are absent from SDK data.
        Returns partial dict to merge into the record.
        Default extracts all standard metadata fields.
        """
        return {
            'report_type': str(row.get('REPORT_TYPE', '')),
            'statement_code': str(row.get('STATEMENT_TYPE', '')),
            'security_name': str(row.get('SECURITY_NAME', '')),
            'ann_date': str(row.get('ANN_DATE', '')),
            'actual_ann_date': str(row.get('ACTUAL_ANN_DATE', '')),
            'comp_type_code': int(row.get('COMP_TYPE_CODE', 0)) if not pd.isna(row.get('COMP_TYPE_CODE')) else 0,
        }

    def post_process(self, ctx: TaskContext, result) -> List[Dict[str, Any]]:
        processed = []
        frames = self._normalize_result(result)

        for df in frames:
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for _, row in df.iterrows():
                symbol = str(row.get('MARKET_CODE', '')).strip()
                reporting_period = str(row.get('REPORTING_PERIOD', '')).strip()
                if not symbol or not reporting_period:
                    continue

                # Build data_json from all non-metadata columns
                data_fields = {}
                for col in df.columns:
                    if col in METADATA_FIELDS:
                        continue
                    val = row.get(col)
                    if pd.isna(val):
                        continue
                    if hasattr(val, 'item'):
                        val = val.item()
                    data_fields[col] = val

                record = {
                    'source': consts.DataSource.DS_AMAZING_DATA.value,
                    'symbol': symbol,
                    'market': 'zh_a',
                    'statement_type': self.STATEMENT_TYPE,
                    'reporting_period': reporting_period,
                    'data_json': json.dumps(data_fields, ensure_ascii=False),
                }
                record.update(self._get_metadata_overrides(row))
                processed.append(record)

        ctx.logger.info({
            'event': f'{self.STATEMENT_TYPE}_post_process_done',
            'total_records': len(processed),
            'run_id': ctx.run_id,
        })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': f'{self.STATEMENT_TYPE}_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)

        batch_size = 500
        for i in range(0, len(processed), batch_size):
            batch = processed[i:i + batch_size]
            ok = phoenixA_client.upsert_financial_statements(
                batch,
                data_source=consts.DataSource.DS_AMAZING_DATA.value,
                statement_type=self.STATEMENT_TYPE,
                run_id=ctx.run_id,
            )
            if ok is False:
                ctx.fail(f"failed to sink {self.STATEMENT_TYPE} batch {i // batch_size} to phoenixA", phase='sink')
                return

        ctx.logger.info({
            'event': f'{self.STATEMENT_TYPE}_sink_done',
            'total_records': len(processed),
            'run_id': ctx.run_id,
        })


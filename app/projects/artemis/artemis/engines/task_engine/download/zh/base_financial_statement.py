"""
Base class for financial statement download tasks.

Eliminates duplication across balance_sheet, cashflow, income, profit_express, profit_notice tasks.
Subclasses only need to define:
  - STATEMENT_TYPE: str
  - SDK_METHOD_NAME: str
  - _sdk_call(info_data, code_list, cache_dir, **sdk_date_kwargs) -> result
  - (optional) _get_metadata_overrides(row) -> dict  for tasks with missing fields
  - (optional) _normalize_result(result) -> iterable of DataFrames

Supports incremental downloads via ctx.params:
  - symbols: list[str]  — AmazingData format codes, e.g. ['000001.SZ', '600519.SH']
    When absent, downloads full historical code list from SDK.
  - start_date: int  — reporting period start (e.g. 20240101), mapped to SDK begin_date
  - end_date: int    — reporting period end, mapped to SDK end_date

SDK parameter support (per AmazingData_development_guide.md V1.0.24):
  All 5 financial APIs (balance_sheet, cash_flow, income, profit_express, profit_notice)
  accept: code_list (required), local_path, is_local, begin_date (optional), end_date (optional)

PhoenixA upserts are idempotent (ON CONFLICT UPDATE), safe for repeated calls.
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
from artemis.engines.task_engine.download.zh.utils import get_symbols_from_params, get_sdk_date_kwargs, split_market_code, normalize_date_yyyymmdd, get_code_list_from_phoenixa


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

    def execute(self, ctx):
        from artemis.core.config_manager import cfg_mgr

        task_engine_cfg = cfg_mgr.task_engine_config()
        cache_dir = os.path.abspath(task_engine_cfg.amazing_data_cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        try:
            # Resolve code_list: explicit symbols or PhoenixA registry
            explicit_symbols = get_symbols_from_params(ctx)
            if explicit_symbols is not None:
                code_list = explicit_symbols
                mode = 'incremental'
            else:
                code_list = get_code_list_from_phoenixa(ctx)
                mode = 'full'

            if not code_list:
                ctx.fail(f"empty code_list for {self.STATEMENT_TYPE} (mode={mode}; check PhoenixA /api/v2/securities)", phase='execute')
                return None

            # Convert our start_date/end_date to SDK begin_date/end_date
            sdk_date_kwargs = get_sdk_date_kwargs(ctx)

            ctx.logger.info({
                'event': f'{self.STATEMENT_TYPE}_execute_start',
                'code_count': len(code_list),
                'sdk_date_kwargs': sdk_date_kwargs,
                'mode': mode,
                'run_id': ctx.run_id,
            })

            return self._sdk_call(self._info_data, code_list, cache_dir, **sdk_date_kwargs)
        except Exception as e:
            ctx.fail(f"fetch {self.STATEMENT_TYPE} failed: {e}", phase='execute')
            return None

    @abstractmethod
    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        """Call the specific SDK method. Override in subclass.

        sdk_date_kwargs may contain begin_date and/or end_date (int),
        mapped from our unified start_date/end_date params.
        """
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

        def _str(val):
            if pd.isna(val):
                return ''
            return str(val).strip()

        def _int(val):
            if pd.isna(val):
                return 0
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return 0

        return {
            'report_type': _str(row.get('REPORT_TYPE')),
            'statement_code': _str(row.get('STATEMENT_TYPE')),
            'security_name': _str(row.get('SECURITY_NAME')),
            'ann_date': normalize_date_yyyymmdd(_str(row.get('ANN_DATE'))),
            'actual_ann_date': normalize_date_yyyymmdd(_str(row.get('ACTUAL_ANN_DATE'))),
            'comp_type_code': _int(row.get('COMP_TYPE_CODE')),
        }

    def post_process(self, ctx: TaskContext, result) -> List[Dict[str, Any]]:
        processed = []
        frames = self._normalize_result(result)

        for df in frames:
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for row in df.to_dict('records'):
                symbol_val = row.get('MARKET_CODE', '')
                if pd.isna(symbol_val):
                    continue
                market_code = str(symbol_val).strip()
                symbol, market = split_market_code(market_code)

                period_val = row.get('REPORTING_PERIOD', '')
                if pd.isna(period_val):
                    continue
                reporting_period = normalize_date_yyyymmdd(str(period_val).strip())
                if not symbol or not reporting_period:
                    continue

                # Build data_json from all non-metadata columns
                data_fields = {}
                for col, val in row.items():
                    if col in METADATA_FIELDS:
                        continue
                    if pd.isna(val):
                        continue
                    if hasattr(val, 'item'):
                        val = val.item()
                    data_fields[col] = val

                record = {
                    'source': consts.DataSource.DS_AMAZING_DATA.value,
                    'symbol': symbol,
                    'market': market,
                    'statement_type': self.STATEMENT_TYPE,
                    'reporting_period': reporting_period,
                    'data_json': json.dumps(data_fields, ensure_ascii=False),
                }
                record.update(self._get_metadata_overrides(row))
                processed.append(record)

        # Deduplicate by unique key (last occurrence wins).
        # SDK may return duplicate rows for the same (symbol, reporting_period, report_type, statement_code).
        seen = {}
        for i, rec in enumerate(processed):
            key = (rec.get('source', ''), rec.get('symbol', ''), rec.get('market', ''),
                   rec.get('statement_type', ''), rec.get('reporting_period', ''),
                   rec.get('report_type', ''), rec.get('statement_code', ''))
            seen[key] = i
        if len(seen) < len(processed):
            deduped = [processed[i] for i in sorted(seen.values())]
            ctx.logger.info({
                'event': f'{self.STATEMENT_TYPE}_dedup',
                'before': len(processed),
                'after': len(deduped),
                'run_id': ctx.run_id,
            })
            processed = deduped

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


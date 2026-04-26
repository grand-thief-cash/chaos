"""
Base class for corporate action download tasks (dividend, right_issue, etc.).

Subclasses define:
  - ACTION_TYPE: str
  - REPORT_PERIOD_FIELD: str  (SDK column for report year, e.g. 'REPORT_PERIOD' / 'RIGHTSISSUE_YEAR')
  - PROGRESS_FIELD: str       (SDK column for progress code, e.g. 'DIV_PROGRESS' / 'PROGRESS')
  - _sdk_call(info_data, code_list, cache_dir) -> result
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


# Fields extracted as structured DB columns; excluded from data_json.
CORP_ACTION_METADATA_FIELDS = frozenset({
    'MARKET_CODE', 'ANN_DATE',
})


class BaseCorporateActionTask(WorkerUnit):
    """Base for all corporate action download tasks."""

    ACTION_TYPE: str = ""
    REPORT_PERIOD_FIELD: str = ""  # SDK column name for the report year
    PROGRESS_FIELD: str = ""       # SDK column name for the progress code

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
            ctx.fail(f"fetch {self.ACTION_TYPE} failed: {e}", phase='execute')
            return None

    @abstractmethod
    def _sdk_call(self, info_data, code_list, cache_dir):
        raise NotImplementedError

    def _normalize_result(self, result) -> Iterable[pd.DataFrame]:
        if isinstance(result, dict):
            return result.values()
        elif isinstance(result, pd.DataFrame):
            return [result]
        return []

    def _get_all_metadata_fields(self) -> frozenset:
        """All fields that become structured columns (excluded from data_json)."""
        extra = set()
        if self.REPORT_PERIOD_FIELD:
            extra.add(self.REPORT_PERIOD_FIELD)
        if self.PROGRESS_FIELD:
            extra.add(self.PROGRESS_FIELD)
        return CORP_ACTION_METADATA_FIELDS | extra

    def post_process(self, ctx: TaskContext, result) -> List[Dict[str, Any]]:
        processed = []
        frames = self._normalize_result(result)
        all_meta = self._get_all_metadata_fields()

        for df in frames:
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for _, row in df.iterrows():
                symbol = str(row.get('MARKET_CODE', '')).strip()
                if not symbol:
                    continue

                ann_date = str(row.get('ANN_DATE', '')).strip()
                report_period = str(row.get(self.REPORT_PERIOD_FIELD, '')).strip() if self.REPORT_PERIOD_FIELD else ''
                progress_code = str(row.get(self.PROGRESS_FIELD, '')).strip() if self.PROGRESS_FIELD else ''

                # Build data_json from all non-metadata columns
                data_fields = {}
                for col in df.columns:
                    if col in all_meta:
                        continue
                    val = row.get(col)
                    if pd.isna(val):
                        continue
                    if hasattr(val, 'item'):
                        val = val.item()
                    data_fields[col] = val

                processed.append({
                    'source': consts.DataSource.DS_AMAZING_DATA.value,
                    'symbol': symbol,
                    'market': 'zh_a',
                    'action_type': self.ACTION_TYPE,
                    'report_period': report_period,
                    'ann_date': ann_date,
                    'progress_code': progress_code,
                    'data_json': json.dumps(data_fields, ensure_ascii=False),
                })

        ctx.logger.info({
            'event': f'{self.ACTION_TYPE}_post_process_done',
            'total_records': len(processed),
            'run_id': ctx.run_id,
        })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': f'{self.ACTION_TYPE}_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)

        batch_size = 500
        for i in range(0, len(processed), batch_size):
            batch = processed[i:i + batch_size]
            ok = phoenixA_client.upsert_corporate_actions(
                batch,
                data_source=consts.DataSource.DS_AMAZING_DATA.value,
                action_type=self.ACTION_TYPE,
                run_id=ctx.run_id,
            )
            if ok is False:
                ctx.fail(f"failed to sink {self.ACTION_TYPE} batch {i // batch_size} to phoenixA", phase='sink')
                return

        ctx.logger.info({
            'event': f'{self.ACTION_TYPE}_sink_done',
            'total_records': len(processed),
            'run_id': ctx.run_id,
        })


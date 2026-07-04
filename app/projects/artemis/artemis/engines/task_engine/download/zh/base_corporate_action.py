"""
Base class for corporate action download tasks (dividend, right_issue, etc.).

Subclasses define:
  - ACTION_TYPE: str
  - REPORT_PERIOD_FIELD: str  (SDK column for report year, e.g. 'REPORT_PERIOD' / 'RIGHTSISSUE_YEAR')
  - PROGRESS_FIELD: str       (SDK column for progress code, e.g. 'DIV_PROGRESS' / 'PROGRESS')
  - _sdk_call(info_data, code_list, cache_dir, **sdk_date_kwargs) -> result

Supports incremental downloads via ctx.params:
  - symbols: list[str]  — AmazingData format codes, e.g. ['000001.SZ', '600519.SH']
    When absent, downloads full historical code list from SDK.
  - start_date: int  — announcement date start (e.g. 20240101), mapped to SDK begin_date
  - end_date: int    — announcement date end, mapped to SDK end_date

SDK parameter support (per AmazingData_development_guide.md V1.0.24):
  Both corporate action APIs (get_dividend, get_right_issue)
  accept: code_list (required), local_path, is_local, begin_date (optional), end_date (optional)

PhoenixA upserts are idempotent (ON CONFLICT UPDATE), safe for repeated calls.
"""
import os
from abc import abstractmethod
from typing import Any, Dict, List, Iterable

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit
from artemis.engines.task_engine.download.zh.utils import get_security_map_for_task, get_sdk_date_kwargs, normalize_date_yyyymmdd


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

    def execute(self, ctx):
        from artemis.core.config_manager import cfg_mgr

        task_engine_cfg = cfg_mgr.task_engine_config()
        cache_dir = os.path.abspath(task_engine_cfg.amazing_data_cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        try:
            # Resolve security_map: explicit symbols (resolved to security_id) or
            # the full PhoenixA registry. code_list (SDK input) is its keys.
            security_map = get_security_map_for_task(ctx)
            if not security_map:
                ctx.fail(f"empty security_map for {self.ACTION_TYPE} (check PhoenixA /api/v2/securities)", phase='execute')
                return None
            self._security_map = security_map
            code_list = list(security_map.keys())

            # Convert our start_date/end_date to SDK begin_date/end_date
            sdk_date_kwargs = get_sdk_date_kwargs(ctx)

            ctx.logger.info({
                'event': f'{self.ACTION_TYPE}_execute_start',
                'code_count': len(code_list),
                'sdk_date_kwargs': sdk_date_kwargs,
                'run_id': ctx.run_id,
            })

            return self._sdk_call(self._info_data, code_list, cache_dir, **sdk_date_kwargs)
        except Exception as e:
            ctx.fail(f"fetch {self.ACTION_TYPE} failed: {e}", phase='execute')
            return None

    @abstractmethod
    def _sdk_call(self, info_data, code_list, cache_dir, **sdk_date_kwargs):
        """Call the specific SDK method. Override in subclass.

        sdk_date_kwargs may contain begin_date and/or end_date (int),
        mapped from our unified start_date/end_date params.
        """
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
        skipped_empty_ann = 0
        skipped_no_security_id = 0
        frames = self._normalize_result(result)
        all_meta = self._get_all_metadata_fields()
        security_map = getattr(self, '_security_map', {})

        for df in frames:
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for row in df.to_dict('records'):
                symbol_val = row.get('MARKET_CODE', '')
                if pd.isna(symbol_val):
                    continue
                market_code = str(symbol_val).strip()
                if not market_code:
                    continue
                sec_info = security_map.get(market_code)
                if not sec_info:
                    # MARKET_CODE not in registry → cannot resolve security_id.
                    # Skip (Phase 3 orphan defense: registry is the only source).
                    skipped_no_security_id += 1
                    continue
                security_id = sec_info["security_id"]

                ann_date_val = row.get('ANN_DATE', '')
                ann_date = normalize_date_yyyymmdd('' if pd.isna(ann_date_val) else str(ann_date_val).strip())

                report_period_val = row.get(self.REPORT_PERIOD_FIELD, '') if self.REPORT_PERIOD_FIELD else ''
                report_period_raw = '' if pd.isna(report_period_val) else str(report_period_val).strip()
                report_period = normalize_date_yyyymmdd(report_period_raw)

                progress_val = row.get(self.PROGRESS_FIELD, '') if self.PROGRESS_FIELD else ''
                progress_code = '' if pd.isna(progress_val) else str(progress_val).strip()

                if not ann_date:
                    skipped_empty_ann += 1
                    continue

                # Build data_json from all non-metadata columns
                data_fields = {}
                for col, val in row.items():
                    if col in all_meta:
                        continue
                    if pd.isna(val):
                        continue
                    if hasattr(val, 'item'):
                        val = val.item()
                    data_fields[col] = val

                processed.append({
                    'security_id': security_id,
                    'source': consts.DataSource.DS_AMAZING_DATA.value,
                    'action_type': self.ACTION_TYPE,
                    'report_period': report_period,
                    'ann_date': ann_date,
                    'progress_code': progress_code,
                    'data_json': data_fields,
                })

        # Deduplicate by unique key (last occurrence wins).
        seen = {}
        for i, rec in enumerate(processed):
            key = (rec.get('security_id', 0), rec.get('source', ''),
                   rec.get('action_type', ''), rec.get('report_period', ''),
                   rec.get('ann_date', ''))
            seen[key] = i
        if len(seen) < len(processed):
            deduped = [processed[i] for i in sorted(seen.values())]
            ctx.logger.info({
                'event': f'{self.ACTION_TYPE}_dedup',
                'before': len(processed),
                'after': len(deduped),
                'run_id': ctx.run_id,
            })
            processed = deduped

        ctx.logger.info({
            'event': f'{self.ACTION_TYPE}_post_process_done',
            'total_records': len(processed),
            'skipped_empty_ann_date': skipped_empty_ann,
            'skipped_no_security_id': skipped_no_security_id,
            'run_id': ctx.run_id,
        })
        if skipped_empty_ann > 0:
            ctx.logger.warning({
                'event': f'{self.ACTION_TYPE}_skipped_empty_ann_date',
                'skipped_count': skipped_empty_ann,
                'run_id': ctx.run_id,
                'reason': 'ann_date is empty, skipping to avoid unique key collision',
            })
        if skipped_no_security_id > 0:
            ctx.logger.warning({
                'event': f'{self.ACTION_TYPE}_skipped_no_security_id',
                'skipped_count': skipped_no_security_id,
                'run_id': ctx.run_id,
                'reason': 'MARKET_CODE not in security_registry; ensure STOCK_ZH_A_LIST has upserted it',
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


import os
from typing import Any, Dict, Iterable, List

import AmazingData as ad
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.download.zh.utils import (
    get_security_map_for_task,
    get_sdk_date_kwargs,
    normalize_date_yyyymmdd,
)
from artemis.engines.task_engine.worker_unit import WorkerUnit

class StockZHALongHuBang(WorkerUnit):
    """下载沪深A股龙虎榜数据（来源：AmazingData InfoData get_long_hu_bang）。

    支持增量下载参数（ctx.params）：
      - symbols: list[str]  — 指定证券代码（纯代码，需配合 exchange）
      - start_date / end_date: YYYY-MM-DD — 交易日期范围
    """

    DATASET_TYPE = "long_hu_bang"

    def before_execute(self, ctx: TaskContext) -> None:
        from artemis.consts import SDK_NAME
        from artemis.core.sdk.manager import sdk_mgr

        try:
            sdk_mgr.get_sdk(SDK_NAME.AMAZING_DATA)
        except Exception as e:
            ctx.fail(f"failed to acquire AmazingData SDK: {e}", phase='before_execute')
            return

        self._info_data = ad.InfoData()  # type: ignore[attr-defined]

    def execute(self, ctx):
        from artemis.core.config_manager import cfg_mgr

        task_engine_cfg = cfg_mgr.task_engine_config()
        cache_dir = os.path.abspath(task_engine_cfg.amazing_data_cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        try:
            security_map = get_security_map_for_task(ctx)
            if not security_map:
                ctx.fail(
                    f"empty security_map for {self.DATASET_TYPE} (check PhoenixA /api/v2/securities)",
                    phase='execute',
                )
                return None
            self._security_map = security_map
            code_list = list(security_map.keys())

            sdk_date_kwargs = get_sdk_date_kwargs(ctx)
            ctx.logger.info({
                'event': f'{self.DATASET_TYPE}_execute_start',
                'code_count': len(code_list),
                'sdk_date_kwargs': sdk_date_kwargs,
                'run_id': ctx.run_id,
            })

            return self._info_data.get_long_hu_bang(
                code_list,
                local_path=cache_dir,
                is_local=False,
                **sdk_date_kwargs,
            )
        except Exception as e:
            ctx.fail(f"fetch {self.DATASET_TYPE} failed: {e}", phase='execute')
            return None

    def _normalize_result(self, result) -> Iterable[pd.DataFrame]:
        if isinstance(result, dict):
            return result.values()
        if isinstance(result, pd.DataFrame):
            return [result]
        return []

    @staticmethod
    def _to_int(val: Any) -> int:
        if pd.isna(val):
            return 0
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_str(val: Any) -> str:
        if pd.isna(val):
            return ''
        return str(val).strip()

    @staticmethod
    def _to_float(val: Any) -> float:
        if pd.isna(val):
            return 0.0
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    def post_process(self, ctx: TaskContext, result) -> List[Dict[str, Any]]:
        processed: List[Dict[str, Any]] = []
        skipped_invalid = 0
        skipped_no_security_id = 0
        security_map = getattr(self, '_security_map', {})

        for df in self._normalize_result(result):
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            for row in df.to_dict('records'):
                market_code = self._to_str(row.get('MARKET_CODE'))
                trade_date = normalize_date_yyyymmdd(self._to_str(row.get('TRADE_DATE')))
                reason_type = self._to_str(row.get('REASON_TYPE'))
                trader_name = self._to_str(row.get('TRADER_NAME'))
                flow_mark = self._to_int(row.get('FLOW_MARK'))

                if not market_code or not trade_date or not reason_type or not trader_name or flow_mark == 0:
                    skipped_invalid += 1
                    continue

                sec_info = security_map.get(market_code)
                if not sec_info:
                    # MARKET_CODE not in registry → cannot resolve security_id.
                    # Skip (Phase 3 orphan defense: registry is the only source).
                    skipped_no_security_id += 1
                    continue
                security_id = sec_info["security_id"]

                processed.append({
                    'security_id': security_id,
                    'source': consts.DataSource.DS_AMAZING_DATA.value,
                    'trade_date': trade_date,
                    'security_name': self._to_str(row.get('SECURITY_NAME')),
                    'reason_type': reason_type,
                    'reason_type_name': self._to_str(row.get('REASON_TYPE_NAME')),
                    'trader_name': trader_name,
                    'flow_mark': flow_mark,
                    'change_range': self._to_float(row.get('CHANGE_RANGE')),
                    'buy_amount': self._to_float(row.get('BUY_AMOUNT')),
                    'sell_amount': self._to_float(row.get('SELL_AMOUNT')),
                    'total_amount': self._to_float(row.get('TOTAL_AMOUNT')),
                    'total_volume': self._to_float(row.get('TOTAL_VOLUME')),
                })

        seen = {}
        for i, rec in enumerate(processed):
            key = (
                rec.get('security_id', 0), rec.get('source', ''),
                rec.get('trade_date', ''), rec.get('reason_type', ''),
                rec.get('trader_name', ''), rec.get('flow_mark', 0),
            )
            seen[key] = i
        if len(seen) < len(processed):
            deduped = [processed[i] for i in sorted(seen.values())]
            ctx.logger.info({
                'event': f'{self.DATASET_TYPE}_dedup',
                'before': len(processed),
                'after': len(deduped),
                'run_id': ctx.run_id,
            })
            processed = deduped

        ctx.logger.info({
            'event': f'{self.DATASET_TYPE}_post_process_done',
            'total_records': len(processed),
            'skipped_invalid_rows': skipped_invalid,
            'skipped_no_security_id': skipped_no_security_id,
            'run_id': ctx.run_id,
        })
        if skipped_no_security_id > 0:
            ctx.logger.warning({
                'event': f'{self.DATASET_TYPE}_skipped_no_security_id',
                'skipped_count': skipped_no_security_id,
                'run_id': ctx.run_id,
                'reason': 'MARKET_CODE not in security_registry; ensure STOCK_ZH_A_LIST has upserted it',
            })
        return processed

    def sink(self, ctx, processed: List[Dict[str, Any]]):
        if not processed:
            ctx.logger.info({'event': f'{self.DATASET_TYPE}_sink_skip', 'reason': 'empty', 'run_id': ctx.run_id})
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        upsert_fn = getattr(phoenixA_client, 'upsert_long_hu_bang', None)
        if upsert_fn is None:
            ctx.fail('PhoenixA client missing upsert_long_hu_bang support', phase='sink')
            return
        batch_size = 500

        for i in range(0, len(processed), batch_size):
            batch = processed[i:i + batch_size]
            ok = upsert_fn(
                batch,
                data_source=consts.DataSource.DS_AMAZING_DATA.value,
                run_id=ctx.run_id,
            )
            if ok is False:
                ctx.fail(f"failed to sink {self.DATASET_TYPE} batch {i // batch_size} to phoenixA", phase='sink')
                return

        ctx.logger.info({
            'event': f'{self.DATASET_TYPE}_sink_done',
            'total_records': len(processed),
            'run_id': ctx.run_id,
        })




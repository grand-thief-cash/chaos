"""WorkerUnit: 复权因子下载子任务 (baostock query_adjust_factor)。

下载单个 symbol 在指定日期区间内的复权因子数据。

数据字段：
  - dividOperateDate: 除权除息日期
  - foreAdjustFactor: 向前复权因子
  - backAdjustFactor: 向后复权因子
  - adjustFactor: 本次复权因子

存储：独立表 adjust_factor（窄表，不保留 JSONB 扩展字段）
"""
from typing import Any, Dict, List

import baostock as bs
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.task_engine.download.zh.utils import normalize_date_yyyymmdd
from artemis.engines.task_engine.worker_unit import WorkerUnit


def _safe_float(val):
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


class StockZhABsAdjustFactorChild(WorkerUnit):

    def execute(self, ctx: TaskContext):
        params = ctx.params
        bs_code = params.get("bs_code")
        symbol = params.get("symbol")
        start_date = params.get("start_date") or "2015-01-01"
        end_date = params.get("end_date") or ""

        rs = bs.query_adjust_factor(code=bs_code, start_date=start_date, end_date=end_date)
        if rs.error_code != '0':
            ctx.fail(
                f"baostock query_adjust_factor failed for {bs_code}: {rs.error_code} {rs.error_msg}",
                phase='execute',
            )
            return None

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            ctx.logger.info({
                "event": "bs_adjust_factor_child_no_data",
                "run_id": ctx.run_id,
                "symbol": symbol,
                "bs_code": bs_code,
                "start_date": start_date,
                "end_date": end_date,
            })
            return None

        df = pd.DataFrame(data_list, columns=rs.fields)
        df["symbol"] = symbol
        df["bs_code"] = bs_code
        return df

    def post_process(self, ctx: TaskContext, result) -> List[Dict[str, Any]]:
        if result is None or (isinstance(result, pd.DataFrame) and result.empty):
            return []

        security_id = ctx.params.get("security_id")
        if not security_id:
            # No security_id forwarded by parent → cannot write (Phase 3).
            ctx.fail("adjust_factor child missing security_id param", phase='post_process')
            return []

        processed = []
        for row in result.to_dict('records'):
            divid_operate_date = normalize_date_yyyymmdd(row.get('dividOperateDate', ''))
            if not divid_operate_date:
                continue

            record = {
                'security_id': int(security_id),
                'source': consts.DataSource.DS_BAOSTOCK.value,
                'divid_operate_date': divid_operate_date,
                'fore_adjust_factor': _safe_float(row.get('foreAdjustFactor')),
                'back_adjust_factor': _safe_float(row.get('backAdjustFactor')),
                'adjust_factor': _safe_float(row.get('adjustFactor')),
            }
            processed.append(record)

        seen = {}
        for i, rec in enumerate(processed):
            key = (rec['security_id'], rec['source'], rec['divid_operate_date'])
            seen[key] = i
        if len(seen) < len(processed):
            processed = [processed[i] for i in sorted(seen.values())]

        ctx.logger.info({
            'event': 'bs_adjust_factor_child_post_process_done',
            'run_id': ctx.run_id,
            'total_records': len(processed),
        })
        return processed

    def sink(self, ctx: TaskContext, processed):
        if not processed:
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
        client: PhoenixAClient = phoenixA_client
        batch_size = 500
        for i in range(0, len(processed), batch_size):
            batch = processed[i:i + batch_size]
            ok = client.upsert_adjust_factors(
                batch,
                data_source=consts.DataSource.DS_BAOSTOCK.value,
                run_id=ctx.run_id,
            )
            if ok is False:
                ctx.fail(
                    f"failed to sink adjust_factor batch {i // batch_size} to phoenixA",
                    phase='sink',
                )
                return

        ctx.logger.info({
            'event': 'bs_adjust_factor_child_sink_done',
            'run_id': ctx.run_id,
            'total_records': len(processed),
        })




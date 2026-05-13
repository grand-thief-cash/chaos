"""WorkerUnit: 季频偿债能力数据下载子任务 (baostock query_balance_data)。

下载单个 symbol 的单个 (year, quarter) 偿债能力数据。

数据字段：
  - currentRatio: 流动比率
  - quickRatio: 速动比率
  - cashRatio: 现金比率
  - YOYLiability: 总负债同比增长率
  - liabilityToAsset: 资产负债率
  - assetToEquity: 权益乘数

存储：复用 financial_statement 表，statement_type = "bs_balance"
"""
import json

import baostock as bs
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


class StockZhABsBalanceChild(WorkerUnit):

    def execute(self, ctx: TaskContext):
        params = ctx.params
        bs_code = params.get("bs_code")
        symbol = params.get("symbol")
        year = params.get("year")
        quarter = params.get("quarter")

        rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)

        if rs.error_code != '0':
            ctx.fail(
                f"baostock query_balance_data failed for {bs_code} {year}Q{quarter}: "
                f"{rs.error_code} {rs.error_msg}",
                phase='execute',
            )
            return None

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            ctx.logger.info({
                "event": "bs_balance_child_no_data",
                "run_id": ctx.run_id,
                "symbol": symbol,
                "year": year,
                "quarter": quarter,
            })
            return None

        df = pd.DataFrame(data_list, columns=rs.fields)
        df['symbol'] = symbol
        return df

    def post_process(self, ctx: TaskContext, result):
        if result is None or (isinstance(result, pd.DataFrame) and result.empty):
            return []

        df = result
        processed = []

        # Fields that become structured columns (excluded from data_json)
        meta_fields = {'code', 'symbol', 'pubDate', 'statDate'}

        for row in df.to_dict('records'):
            stat_date = str(row.get('statDate', '')).strip()
            if not stat_date:
                continue

            # Normalize statDate to YYYY-MM-DD (already in that format from baostock)
            reporting_period = stat_date
            if len(reporting_period) == 10 and reporting_period[4] == '-':
                pass  # already YYYY-MM-DD
            else:
                continue

            pub_date = str(row.get('pubDate', '')).strip()

            # Build data_json from all remaining fields
            data_fields = {}
            for col, val in row.items():
                if col in meta_fields:
                    continue
                if pd.isna(val):
                    continue
                s = str(val).strip()
                if s == '':
                    continue
                # Try to convert to float for numeric fields
                try:
                    data_fields[col] = float(s)
                except (ValueError, TypeError):
                    data_fields[col] = s

            record = {
                'source': consts.DataSource.DS_BAOSTOCK.value,
                'symbol': row.get('symbol', ''),
                'market': 'zh_a',
                'statement_type': 'bs_balance',
                'reporting_period': reporting_period,
                'data_json': json.dumps(data_fields, ensure_ascii=False),
                'ann_date': pub_date if pub_date else '',
                'actual_ann_date': pub_date if pub_date else '',
                'report_type': '',
                'statement_code': '',
                'security_name': '',
                'comp_type_code': 0,
            }
            processed.append(record)

        ctx.logger.info({
            'event': 'bs_balance_child_post_process_done',
            'run_id': ctx.run_id,
            'total_records': len(processed),
        })
        return processed

    def sink(self, ctx: TaskContext, processed):
        if not processed:
            return

        phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)

        batch_size = 500
        for i in range(0, len(processed), batch_size):
            batch = processed[i:i + batch_size]
            ok = phoenixA_client.upsert_financial_statements(
                batch,
                data_source=consts.DataSource.DS_BAOSTOCK.value,
                statement_type='bs_balance',
                run_id=ctx.run_id,
            )
            if ok is False:
                ctx.fail(
                    f"failed to sink bs_balance batch {i // batch_size} to phoenixA",
                    phase='sink',
                )
                return

        ctx.logger.info({
            'event': 'bs_balance_child_sink_done',
            'run_id': ctx.run_id,
            'total_records': len(processed),
        })


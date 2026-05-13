"""WorkerUnit: 除权除息数据下载子任务 (baostock query_dividend_data)。

下载单个 symbol 的单个年份除权除息数据。

数据字段：
  - dividPreNoticeDate: 预批露公告日
  - dividAgmPumDate: 股东大会公告日期
  - dividPlanAnnounceDate: 预案公告日
  - dividPlanDate: 分红实施公告日
  - dividRegistDate: 股权登记日
  - dividOperateDate: 除权除息日期
  - dividPayDate: 派息日
  - dividStockMarketDate: 红股上市交易日
  - dividCashPsBeforeTax: 每股股利税前
  - dividCashPsAfterTax: 每股股利税后
  - dividStocksPs: 每股红股
  - dividCashStock: 分红送转
  - dividReserveToStockPs: 每股转增资本

存储：复用 corporate_action 表，action_type = "bs_dividend"
"""
import json

import baostock as bs
import pandas as pd

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


class StockZhABsDividendChild(WorkerUnit):

    def execute(self, ctx: TaskContext):
        params = ctx.params
        bs_code = params.get("bs_code")
        symbol = params.get("symbol")
        year = params.get("year")
        year_type = params.get("year_type", "report")

        rs = bs.query_dividend_data(code=bs_code, year=year, yearType=year_type)

        if rs.error_code != '0':
            ctx.fail(
                f"baostock query_dividend_data failed for {bs_code} year={year}: "
                f"{rs.error_code} {rs.error_msg}",
                phase='execute',
            )
            return None

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            ctx.logger.info({
                "event": "bs_dividend_child_no_data",
                "run_id": ctx.run_id,
                "symbol": symbol,
                "year": year,
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
        meta_fields = {'code', 'symbol'}

        for row in df.to_dict('records'):
            symbol = str(row.get('symbol', '')).strip()
            if not symbol:
                continue

            # Use dividPlanAnnounceDate as ann_date (most reliable date)
            ann_date = ''
            for date_field in ['dividPlanAnnounceDate', 'dividPlanDate', 'dividOperateDate']:
                val = str(row.get(date_field, '')).strip()
                if val and val != 'None':
                    ann_date = val
                    break

            if not ann_date:
                # Skip records without any announcement date
                continue

            # Use the year param as report_period
            year = ctx.params.get("year", "")
            report_period = f"{year}-12-31" if year else ""

            # Determine progress_code based on available dates
            if str(row.get('dividOperateDate', '')).strip():
                progress_code = 'implemented'  # 已实施
            elif str(row.get('dividPlanDate', '')).strip():
                progress_code = 'announced'  # 已公告
            elif str(row.get('dividPlanAnnounceDate', '')).strip():
                progress_code = 'planned'  # 预案
            else:
                progress_code = 'unknown'

            # Build data_json from all date and value fields
            data_fields = {}
            for col, val in row.items():
                if col in meta_fields:
                    continue
                if pd.isna(val):
                    continue
                s = str(val).strip()
                if s == '' or s == 'None':
                    continue
                # Try numeric conversion for value fields
                try:
                    data_fields[col] = float(s)
                except (ValueError, TypeError):
                    data_fields[col] = s

            record = {
                'source': consts.DataSource.DS_BAOSTOCK.value,
                'symbol': symbol,
                'market': 'zh_a',
                'action_type': 'bs_dividend',
                'report_period': report_period,
                'ann_date': ann_date,
                'progress_code': progress_code,
                'data_json': json.dumps(data_fields, ensure_ascii=False),
            }
            processed.append(record)

        # Deduplicate by unique key (last occurrence wins)
        seen = {}
        for i, rec in enumerate(processed):
            key = (rec['source'], rec['symbol'], rec['market'],
                   rec['action_type'], rec['ann_date'])
            seen[key] = i
        if len(seen) < len(processed):
            deduped = [processed[i] for i in sorted(seen.values())]
            ctx.logger.info({
                'event': 'bs_dividend_child_dedup',
                'before': len(processed),
                'after': len(deduped),
                'run_id': ctx.run_id,
            })
            processed = deduped

        ctx.logger.info({
            'event': 'bs_dividend_child_post_process_done',
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
            ok = phoenixA_client.upsert_corporate_actions(
                batch,
                data_source=consts.DataSource.DS_BAOSTOCK.value,
                action_type='bs_dividend',
                run_id=ctx.run_id,
            )
            if ok is False:
                ctx.fail(
                    f"failed to sink bs_dividend batch {i // batch_size} to phoenixA",
                    phase='sink',
                )
                return

        ctx.logger.info({
            'event': 'bs_dividend_child_sink_done',
            'run_id': ctx.run_id,
            'total_records': len(processed),
        })


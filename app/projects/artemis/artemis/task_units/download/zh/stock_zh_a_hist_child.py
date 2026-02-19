import baostock as bs
import pandas as pd

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.task_units.child import ChildTaskUnit


class StockZhAHistChild(ChildTaskUnit):

    def execute(self, ctx: TaskContext) -> pd.DataFrame:
        """
        Execute the task: Fetch data from baostock.
        """
        params = ctx.params  # Use merged params

        code = params.get("code")
        row_code = params.get("row_code")
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        frequency = params.get("frequency")
        adjustflag = params.get("adjustflag")
        fields_str = params.get("fields")

        rs = bs.query_history_k_data_plus(
            code,
            fields_str,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjustflag=adjustflag
        )

        if rs.error_code != '0':
            ctx.logger.error({
                "event": "stock_zh_a_hist_child_bs_query_error",
                "run_id": ctx.run_id,
                "code": code,
                "error_code": rs.error_code,
                "error_msg": rs.error_msg
            })
            return pd.DataFrame()

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            ctx.logger.info({
                "event": "stock_zh_a_hist_child_no_data",
                "run_id": ctx.run_id,
                "code": code
            })
            return pd.DataFrame()

        df = pd.DataFrame(data_list, columns=fields_str.split(','))
        # Pass row_code along with dataframe using a tuple or adding column here?
        # Adding here is simpler for post_process
        df['code'] = row_code
        return df

    def post_process(self, ctx: TaskContext, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process the data: Type conversion using pandas.
        """
        if df.empty:
            return df

        df.columns = [c.strip() for c in df.columns]

        # Ensure required identifiers exist
        if "code" in df.columns:
            df["code"] = df["code"].astype(str).str.strip()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

        # Required schema fields for PhoenixA
        expected_cols = [
            "date",
            "code",
            "open",
            "high",
            "low",
            "close",
            "preclose",
            "volume",
            "amount",
            "turn",
            "pctChg",
            "peTTM",
            "psTTM",
            "pcfNcfTTM",
            "pbMRQ",
        ]

        float_cols = [
            "open",
            "high",
            "low",
            "close",
            "preclose",
            "turn",
            "pctChg",
            "peTTM",
            "pbMRQ",
            "psTTM",
            "pcfNcfTTM",
        ]
        int_cols = ["volume"]

        for col in float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).round(2)

        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).round(0).astype("int64")

        for col in int_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        # Drop rows missing primary keys to avoid invalid payloads
        if "date" in df.columns and "code" in df.columns:
            df = df[df["date"].notna() & df["code"].notna()]

        # Keep only known fields to avoid unexpected payloads
        df = df[[c for c in expected_cols if c in df.columns]]
        return df

    def sink(self, ctx: TaskContext, df: pd.DataFrame):
        """
        Sink the data: Save to PhoenixA.
        """
        if df.empty:
            return

        # Get PhoenixA client from context directly
        phoenix_client: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]

        params = ctx.params
        code = params.get("code")
        frequency = params.get("frequency")
        adjustflag = params.get("adjustflag")

        # Convert back to list of dicts for the client method
        data_list = df.to_dict('records')

        success = phoenix_client.save_stock_hist_data(data_list, frequency, adjustflag, run_id=ctx.run_id)
        if success:
            ctx.logger.info({
                "event": "stock_zh_a_hist_child_success",
                "run_id": ctx.run_id,
                "code": code,
                "count": len(data_list)
            })
        else:
             ctx.logger.error({
                "event": "stock_zh_a_hist_child_save_failed",
                "run_id": ctx.run_id,
                "code": code
            })

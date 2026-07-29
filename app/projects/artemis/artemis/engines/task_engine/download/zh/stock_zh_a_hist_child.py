import baostock as bs
import pandas as pd
from artemis.engines.task_engine.worker_unit import WorkerUnit

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.clients.phoenixA_client import PhoenixAClient


class StockZhAHistChild(WorkerUnit):

    def execute(self, ctx: TaskContext) -> pd.DataFrame:
        """
        Execute the task: Fetch data from baostock.
        """
        params = ctx.params  # Use merged params

        bs_code = params.get("bs_code")
        symbol = params.get("symbol")
        security_id = params.get("security_id")
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        bs_period = params.get("bs_period")
        bs_adjust = params.get("bs_adjust")
        fields_str = params.get("fields")

        # Phase 4: every bar row must carry a security_id (phoenixA resolves it
        # → physical symbol; a missing/zero id would 400 at upsert). Fail fast
        # rather than fetch data we cannot sink.
        if not security_id:
            ctx.fail(f"missing security_id for symbol={symbol}; registry must upsert it first", phase='execute')
            return pd.DataFrame()

        rs = bs.query_history_k_data_plus(
            bs_code,
            fields_str,
            start_date=start_date,
            end_date=end_date,
            frequency=bs_period,
            adjustflag=bs_adjust
        )

        if rs.error_code != '0':
            err_msg = f"baostock query failed for bs_code={bs_code}: {rs.error_code} {rs.error_msg}"
            ctx.fail(err_msg, phase='execute')
            return pd.DataFrame()

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            ctx.logger.info({
                "event": "stock_zh_a_hist_child_no_data",
                "run_id": ctx.run_id,
                "symbol": symbol,
                "bs_code": bs_code,
            })
            return pd.DataFrame()

        df = pd.DataFrame(data_list, columns=fields_str.split(','))
        # Attach identity (PhoenixA v2 unified field names). security_id is the
        # Phase 4 identity; symbol is kept as the physical storage key (§3.2).
        df['symbol'] = symbol
        df['security_id'] = int(security_id)
        return df

    def post_process(self, ctx: TaskContext, df: pd.DataFrame) -> dict:
        """
        Process the data: Type conversion using pandas.
        Returns a dict with 'bars' (standard OHLCV DataFrame) and 'ext' (baostock extension DataFrame).
        """
        if df.empty:
            return {"bars": df, "ext": pd.DataFrame()}

        df.columns = [c.strip() for c in df.columns]

        # ── Rename baostock fields → PhoenixA v2 unified names ──
        # date → trade_date (symbol is already added in execute)
        if "date" in df.columns:
            df.rename(columns={"date": "trade_date"}, inplace=True)

        # Ensure required identifiers exist and are clean
        if "symbol" in df.columns:
            df["symbol"] = df["symbol"].astype(str).str.strip()
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")

        # ── Standard bars fields (PhoenixA StandardBar) ──
        # security_id is the Phase 4 API identity; symbol is kept as the
        # physical storage key (§3.2). phoenixA resolves security_id → symbol.
        standard_cols = [
            "security_id",
            "trade_date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "preclose",
            "volume",
            "amount",
            "pctChg",
        ]

        # ── Extension fields (PhoenixA BarsExtBaostock) ──
        # Baostock names → PhoenixA snake_case mapping
        ext_rename_map = {
            "turn": "turn",
            "peTTM": "pe_ttm",
            "psTTM": "ps_ttm",
            "pbMRQ": "pb_mrq",
            "pcfNcfTTM": "pcf_ncf_ttm",
            "tradestatus": "trade_status",
            "isST": "is_st",
        }

        required_price_cols = ["open", "high", "low", "close"]
        optional_float_cols = [
            "preclose", "pctChg",
            "turn", "peTTM", "pbMRQ", "psTTM", "pcfNcfTTM",
        ]

        # Core OHLC fields are required for a usable bar. Invalid values reject
        # the row; they must never be silently converted to a plausible zero.
        for col in required_price_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(4)

        # Optional observations preserve unknown as NULL/None. A genuine source
        # value of zero remains zero.
        for col in optional_float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(4)

        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").round(0).astype("Int64")

        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").round(0).astype("Int64")

        if "tradestatus" in df.columns:
            df["tradestatus"] = pd.to_numeric(df["tradestatus"], errors="coerce").astype("Int64")

        if "isST" in df.columns:
            normalized = df["isST"].astype(str).str.strip().str.lower()
            df["isST"] = normalized.map({
                "1": True, "true": True, "yes": True,
                "0": False, "false": False, "no": False,
            }).astype("boolean")

        # Reject rows missing identity/date/core OHLC. Optional values remain
        # nullable; do not drop the whole row for an unavailable valuation.
        valid_mask = pd.Series(True, index=df.index)
        for col in ("security_id", "trade_date", "symbol", *required_price_cols):
            if col not in df.columns:
                valid_mask &= False
                continue
            valid_mask &= df[col].notna()
        if "trade_date" in df.columns:
            valid_mask &= df["trade_date"] != ""
        if "symbol" in df.columns:
            valid_mask &= df["symbol"].astype(str).str.strip() != ""

        rejected_count = int((~valid_mask).sum())
        if rejected_count:
            ctx.logger.warning({
                "event": "stock_zh_a_hist_child_rows_rejected",
                "run_id": ctx.run_id,
                "symbol": ctx.params.get("symbol"),
                "rejected_count": rejected_count,
                "reason": "missing identity/date/core_ohlc",
            })
        df = df[valid_mask].copy()

        # Rename pctChg → pct_chg to match PhoenixA StandardBar JSON tag
        if "pctChg" in df.columns:
            df.rename(columns={"pctChg": "pct_chg"}, inplace=True)
            standard_cols = [c if c != "pctChg" else "pct_chg" for c in standard_cols]

        # Build standard bars DataFrame
        bars_df = df[[c for c in standard_cols if c in df.columns]].copy()

        # Build ext DataFrame (security_id + trade_date + symbol + ext columns)
        ext_src_cols = [k for k in ext_rename_map if k in df.columns]
        if ext_src_cols:
            ext_base = ["security_id", "trade_date", "symbol"] if "security_id" in df.columns else ["trade_date", "symbol"]
            ext_df = df[ext_base + ext_src_cols].copy()
            ext_df.rename(columns=ext_rename_map, inplace=True)
        else:
            ext_df = pd.DataFrame()

        # pandas nullable dtypes must become Python None before requests/json
        # serialization; otherwise pd.NA/NaN may leak into an invalid payload.
        bars_df = bars_df.astype(object).where(pd.notna(bars_df), None)
        if not ext_df.empty:
            ext_df = ext_df.astype(object).where(pd.notna(ext_df), None)

        return {"bars": bars_df, "ext": ext_df}

    def sink(self, ctx: TaskContext, processed: dict):
        """
        Sink the data: Save to PhoenixA via v2 API.
        processed = {"bars": DataFrame, "ext": DataFrame}
        """
        bars_df = processed.get("bars", pd.DataFrame())
        ext_df = processed.get("ext", pd.DataFrame())

        if bars_df.empty:
            return

        # Get PhoenixA client from context directly
        phoenix_client: PhoenixAClient = ctx.dept_http[DeptServices.PHOENIXA]

        params = ctx.params
        symbol = params.get("symbol")
        period = params.get("period")
        adjust = params.get("adjust")

        # Convert DataFrames to list of dicts for the client method
        bars_list = bars_df.to_dict('records')
        ext_list = ext_df.to_dict('records') if not ext_df.empty else None

        success = phoenix_client.upsert_bars(
            period=period,
            adjust=adjust,
            source="baostock",
            bars=bars_list,
            ext=ext_list,
            run_id=ctx.run_id,
        )
        if success:
            ctx.logger.info({
                "event": "stock_zh_a_hist_child_success",
                "run_id": ctx.run_id,
                "symbol": symbol,
                "bars_count": len(bars_list),
                "ext_count": len(ext_list) if ext_list else 0,
            })
        else:
            ctx.fail(f"failed to sink stock hist for symbol={symbol}", phase='sink')


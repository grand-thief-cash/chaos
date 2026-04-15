"""Tests for code→symbol v2 field naming in StockZhAHistChild and StockZhAHistParent.

Validates that:
- post_process outputs trade_date/symbol (not date/code)
- bars and ext are split correctly
- ext fields are renamed to snake_case
- empty trade_date rows are dropped
- sink calls upsert_bars (v2 API) with correct field names
- parent plan emits bs_code/symbol params (not code/raw_code)
- get_securities return without "code" field works
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Any, Dict, List, Optional

import pandas as pd

from artemis.engines.task_engine.download.zh.stock_zh_a_hist_child import StockZhAHistChild
from artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent import StockZhAHistParent


# ── Helpers ──

def _make_baostock_df(symbol: str = "600000", rows: int = 3) -> pd.DataFrame:
    """Simulate a DataFrame as returned by execute() — baostock fields + symbol column."""
    data = []
    for i in range(rows):
        data.append({
            "date": f"2024-01-{10 + i:02d}",
            "open": str(10.0 + i),
            "high": str(11.0 + i),
            "low": str(9.0 + i),
            "close": str(10.5 + i),
            "preclose": str(10.0 + i),
            "volume": str(1000 + i * 100),
            "amount": str(100000 + i * 10000),
            "turn": str(1.5 + i * 0.1),
            "pctChg": str(0.5 + i * 0.1),
            "peTTM": str(15.0 + i),
            "pbMRQ": str(2.0 + i * 0.1),
            "psTTM": str(3.0 + i * 0.1),
            "pcfNcfTTM": str(4.0 + i * 0.1),
        })
    df = pd.DataFrame(data)
    df["symbol"] = symbol
    return df


def _make_ctx_mock(params: dict, run_id="test:1"):
    """Create a minimal TaskContext mock."""
    ctx = MagicMock()
    ctx.params = dict(params)
    ctx.run_id = run_id
    ctx.incoming_params = dict(params)
    ctx.logger = MagicMock()
    ctx.has_failed.return_value = False
    ctx.error = None
    ctx.failed_phase = None
    return ctx


class FakePhoenixClient:
    """Fake PhoenixA client recording upsert_bars calls."""

    def __init__(self, upsert_ok=True):
        self.upsert_calls: List[Dict[str, Any]] = []
        self._upsert_ok = upsert_ok

    def upsert_bars(self, *, asset_type="stock", market="zh_a",
                    period, adjust, source="", bars, ext=None, run_id=None):
        self.upsert_calls.append({
            "asset_type": asset_type,
            "market": market,
            "period": period,
            "adjust": adjust,
            "source": source,
            "bars": bars,
            "ext": ext,
            "run_id": run_id,
        })
        return self._upsert_ok

    def get_securities(self, *, symbols=None, asset_type="stock", market="zh_a",
                       exchanges=None, limit=20000):
        syms = symbols or ["600000", "000001"]
        return {s: {"symbol": s, "exchange": "SH"} for s in syms}

    def get_bars_last_update(self, *, asset_type="stock", market="zh_a",
                             period="daily", adjust="nf", symbols=None):
        return {}


# ── post_process tests ──

class TestPostProcessFieldNames(unittest.TestCase):
    """post_process must output trade_date/symbol, never date/code."""

    def setUp(self):
        self.child = StockZhAHistChild()
        self.ctx = _make_ctx_mock({})

    def test_date_renamed_to_trade_date(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        self.assertIn("trade_date", bars_df.columns)
        self.assertNotIn("date", bars_df.columns)

    def test_symbol_column_present_not_code(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        self.assertIn("symbol", bars_df.columns)
        self.assertNotIn("code", bars_df.columns)

    def test_symbol_value_is_plain_code(self):
        df = _make_baostock_df(symbol="000001")
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        self.assertTrue((bars_df["symbol"] == "000001").all())

    def test_trade_date_format_yyyy_mm_dd(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        for d in bars_df["trade_date"]:
            self.assertRegex(d, r"^\d{4}-\d{2}-\d{2}$")

    def test_pctChg_renamed_to_pct_chg(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        self.assertIn("pct_chg", bars_df.columns)
        self.assertNotIn("pctChg", bars_df.columns)


class TestPostProcessBarExtSplit(unittest.TestCase):
    """post_process must split standard bars and baostock ext data."""

    def setUp(self):
        self.child = StockZhAHistChild()
        self.ctx = _make_ctx_mock({})

    def test_bars_contains_standard_fields(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        expected = {"trade_date", "symbol", "open", "high", "low", "close",
                    "preclose", "volume", "amount", "pct_chg"}
        self.assertEqual(set(bars_df.columns), expected)

    def test_ext_contains_extension_fields(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        ext_df = result["ext"]
        expected = {"trade_date", "symbol", "turn", "pe_ttm", "ps_ttm", "pb_mrq", "pcf_ncf_ttm"}
        self.assertEqual(set(ext_df.columns), expected)

    def test_ext_fields_renamed_to_snake_case(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        ext_df = result["ext"]
        # Must NOT contain original camelCase names
        self.assertNotIn("peTTM", ext_df.columns)
        self.assertNotIn("psTTM", ext_df.columns)
        self.assertNotIn("pbMRQ", ext_df.columns)
        self.assertNotIn("pcfNcfTTM", ext_df.columns)

    def test_bars_does_not_contain_ext_fields(self):
        df = _make_baostock_df()
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        ext_only = {"turn", "pe_ttm", "ps_ttm", "pb_mrq", "pcf_ncf_ttm",
                     "peTTM", "psTTM", "pbMRQ", "pcfNcfTTM"}
        self.assertEqual(set(bars_df.columns) & ext_only, set())

    def test_empty_df_returns_empty_bars_and_ext(self):
        result = self.child.post_process(self.ctx, pd.DataFrame())
        self.assertTrue(result["bars"].empty)
        self.assertTrue(result["ext"].empty)


class TestPostProcessDataCleaning(unittest.TestCase):
    """post_process drops invalid rows."""

    def setUp(self):
        self.child = StockZhAHistChild()
        self.ctx = _make_ctx_mock({})

    def test_rows_with_empty_trade_date_dropped(self):
        df = _make_baostock_df(rows=2)
        df.loc[0, "date"] = ""
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        self.assertEqual(len(bars_df), 1)

    def test_rows_with_nan_trade_date_dropped(self):
        df = _make_baostock_df(rows=2)
        df.loc[0, "date"] = "invalid-date"
        result = self.child.post_process(self.ctx, df)
        bars_df = result["bars"]
        self.assertEqual(len(bars_df), 1)


# ── sink tests ──

class TestSinkCallsV2API(unittest.TestCase):
    """sink must call upsert_bars (v2) not upsert_stock_zh_a_hist (legacy)."""

    def setUp(self):
        self.child = StockZhAHistChild()
        self.fake_client = FakePhoenixClient()

    def _make_sink_ctx(self, symbol="600000"):
        ctx = _make_ctx_mock({
            "symbol": symbol,
            "period": "daily",
            "adjust": "hfq",
        })
        ctx.dept_http = {"phoenixA": self.fake_client}
        return ctx

    def test_sink_calls_upsert_bars(self):
        ctx = self._make_sink_ctx()
        df = _make_baostock_df()
        processed = self.child.post_process(ctx, df)
        self.child.sink(ctx, processed)

        self.assertEqual(len(self.fake_client.upsert_calls), 1)
        call = self.fake_client.upsert_calls[0]
        self.assertEqual(call["period"], "daily")
        self.assertEqual(call["adjust"], "hfq")
        self.assertEqual(call["source"], "baostock")

    def test_sink_bars_have_trade_date_and_symbol(self):
        ctx = self._make_sink_ctx(symbol="000001")
        df = _make_baostock_df(symbol="000001")
        processed = self.child.post_process(ctx, df)
        self.child.sink(ctx, processed)

        bars = self.fake_client.upsert_calls[0]["bars"]
        for bar in bars:
            self.assertIn("trade_date", bar)
            self.assertIn("symbol", bar)
            self.assertNotIn("date", bar)
            self.assertNotIn("code", bar)
            self.assertEqual(bar["symbol"], "000001")

    def test_sink_ext_has_snake_case_fields(self):
        ctx = self._make_sink_ctx()
        df = _make_baostock_df()
        processed = self.child.post_process(ctx, df)
        self.child.sink(ctx, processed)

        ext = self.fake_client.upsert_calls[0]["ext"]
        self.assertIsNotNone(ext)
        for row in ext:
            self.assertIn("pe_ttm", row)
            self.assertIn("pb_mrq", row)
            self.assertNotIn("peTTM", row)
            self.assertNotIn("pbMRQ", row)

    def test_sink_empty_bars_skips_upsert(self):
        ctx = self._make_sink_ctx()
        processed = {"bars": pd.DataFrame(), "ext": pd.DataFrame()}
        self.child.sink(ctx, processed)
        self.assertEqual(len(self.fake_client.upsert_calls), 0)

    def test_sink_failure_calls_ctx_fail(self):
        self.fake_client._upsert_ok = False
        ctx = self._make_sink_ctx(symbol="600000")
        df = _make_baostock_df()
        processed = self.child.post_process(ctx, df)
        self.child.sink(ctx, processed)

        ctx.fail.assert_called_once()
        args = ctx.fail.call_args
        self.assertIn("symbol=600000", str(args))
        self.assertNotIn("code=", str(args))


# ── parent plan tests ──

class TestParentPlanUsesSymbol(unittest.TestCase):
    """Parent plan must emit bs_code/symbol params, not code/raw_code."""

    def setUp(self):
        self.parent = StockZhAHistParent()

    def test_child_params_use_bs_code_and_symbol(self):
        ctx = _make_ctx_mock({
            "period": "daily",
            "adjust": "hfq",
            "start_date": "2024-01-01",
            "fields": "date,open,close",
            "symbol_infos": {
                "600000": {"symbol": "600000", "exchange": "SH"},
            },
            "last_updates_map": {},
        })

        with patch("artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent.convert_to_baostock_params",
                   side_effect=lambda n, v: "d" if n == "frequency" else "1"):
            specs = self.parent.plan(ctx)

        self.assertEqual(len(specs), 1)
        child_params = specs[0]["params"]

        # Must have bs_code and symbol, NOT code and raw_code
        self.assertIn("bs_code", child_params)
        self.assertIn("symbol", child_params)
        self.assertNotIn("code", child_params)
        self.assertNotIn("raw_code", child_params)

        self.assertEqual(child_params["bs_code"], "sh.600000")
        self.assertEqual(child_params["symbol"], "600000")

    def test_plan_works_without_code_field_in_symbol_infos(self):
        """get_securities() no longer returns 'code' — plan must still work."""
        ctx = _make_ctx_mock({
            "period": "daily",
            "adjust": "nf",
            "start_date": "2024-01-01",
            "fields": "date,open,close",
            "symbol_infos": {
                "000001": {"symbol": "000001", "exchange": "SZ"},
            },
            "last_updates_map": {},
        })

        with patch("artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent.convert_to_baostock_params",
                   side_effect=lambda n, v: "d" if n == "frequency" else "3"):
            specs = self.parent.plan(ctx)

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["params"]["symbol"], "000001")
        self.assertEqual(specs[0]["params"]["bs_code"], "sz.000001")

    def test_plan_skips_up_to_date_symbols(self):
        ctx = _make_ctx_mock({
            "period": "daily",
            "adjust": "nf",
            "start_date": "2020-01-01",
            "fields": "date,open,close",
            "symbol_infos": {
                "600000": {"symbol": "600000", "exchange": "SH"},
            },
            "last_updates_map": {"600000": "2099-12-31"},
        })

        with patch("artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent.convert_to_baostock_params",
                   side_effect=lambda n, v: "d" if n == "frequency" else "3"):
            specs = self.parent.plan(ctx)

        self.assertEqual(len(specs), 0)

    def test_plan_log_uses_total_symbols(self):
        ctx = _make_ctx_mock({
            "period": "daily",
            "adjust": "nf",
            "start_date": "2024-01-01",
            "fields": "date,open,close",
            "symbol_infos": {
                "600000": {"symbol": "600000", "exchange": "SH"},
                "000001": {"symbol": "000001", "exchange": "SZ"},
            },
            "last_updates_map": {},
        })

        with patch("artemis.engines.task_engine.download.zh.stock_zh_a_hist_parent.convert_to_baostock_params",
                   side_effect=lambda n, v: "d" if n == "frequency" else "1"):
            self.parent.plan(ctx)

        log_call = ctx.logger.info.call_args_list[-1]
        log_dict = log_call[0][0]
        self.assertIn("total_symbols", log_dict)
        self.assertNotIn("total_codes", log_dict)
        self.assertEqual(log_dict["total_symbols"], 2)


# ── get_securities return format ──

class TestGetSecuritiesNoCodeField(unittest.TestCase):
    """get_securities no longer returns 'code' field."""

    def test_return_dict_has_symbol_not_code(self):
        from artemis.core.clients.phoenixA_client import PhoenixAClient

        client = PhoenixAClient.__new__(PhoenixAClient)
        client.logger = None

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "data": [
                {"symbol": "600000", "name": "浦发银行", "exchange": "SH"},
                {"symbol": "000001", "name": "平安银行", "exchange": "SZ"},
            ]
        }

        with patch.object(client, "get", return_value=fake_resp):
            result = client.get_securities()

        self.assertEqual(len(result), 2)
        for sym, info in result.items():
            self.assertIn("symbol", info)
            self.assertNotIn("code", info)
            self.assertEqual(info["symbol"], sym)


if __name__ == "__main__":
    unittest.main()


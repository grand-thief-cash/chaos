from __future__ import annotations

import json
from importlib import import_module

import pandas as pd

from artemis.consts import DeptServices
from artemis.engines.task_engine.download.risk_download_utils import (
    incremental_start_date,
    within_date_range,
)
from artemis.engines.task_engine.download.us.stock_us_daily import StockUSDaily
from artemis.engines.task_engine.download.us.stock_us_list import StockUSList
from artemis.engines.task_engine.download.zh.index_zh_a_daily import IndexZhADaily
from artemis.engines.task_engine.download.zh.index_zh_a_option_qvix import (
    IndexZhAOptionQVIX,
)
from artemis.engines.task_engine.download.zh.option_zh_a_daily_stats import (
    OptionZhADailyStats,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_hsgt_hist import (
    StockZhAHsgtHist,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_margin_summary import (
    StockZhAMarginSummary,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_disclosure_schedule import (
    StockZhADisclosureSchedule,
    disclosure_periods,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_list import (
    SECURITY_TYPE_SPECS,
    StockZHAList,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_notice import StockZhANotice


configured_specs = import_module(
    "artemis.engines.task_engine.download.global.bar_utils",
).configured_specs
GlobalCommodityDaily = import_module(
    "artemis.engines.task_engine.download.global.commodity_daily",
).GlobalCommodityDaily
GlobalIndexDaily = import_module(
    "artemis.engines.task_engine.download.global.index_daily",
).GlobalIndexDaily
GlobalRateDaily = import_module(
    "artemis.engines.task_engine.download.global.rate_daily",
).GlobalRateDaily
GlobalSecurityList = import_module(
    "artemis.engines.task_engine.download.global.security_list",
).GlobalSecurityList
RATE_SERIES = import_module(
    "artemis.engines.task_engine.download.global.series",
).RATE_SERIES


class FakeLogger:
    def info(self, _message):
        pass

    def warning(self, _message):
        pass


class FakeCtx:
    def __init__(self, params=None):
        self.params = params or {}
        self.run_id = "risk-test"
        self.logger = FakeLogger()
        self.stats = {}


def test_within_date_range_incremental_overrides_historical_start():
    today = pd.Timestamp.now().normalize()
    old = (today - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    recent = (today - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    params = {"mode": "incremental", "lookback_days": 10, "start_date": "2015-01-01"}
    assert within_date_range(recent, params)
    assert not within_date_range(old, params)


def test_incremental_start_uses_max_of_config_and_last_update_plus_one():
    assert incremental_start_date(
        "2026-07-01", "2026-07-10", "2015-01-01",
    ) == "2026-07-11"
    assert incremental_start_date(
        "2026-07-20", "2026-07-10", "2015-01-01",
    ) == "2026-07-20"
    assert incremental_start_date(
        None, None, "2015-01-01",
    ) == "2015-01-01"


def test_index_zh_a_post_process_preserves_optional_null():
    task = IndexZhADaily()
    task._security_by_code = {
        "000300.SH": {"security_id": 7, "symbol": "000300"},
    }
    frame = pd.DataFrame([{
        "kline_time": "2026-07-27",
        "open": 4000,
        "high": 4050,
        "low": 3980,
        "close": 4020,
        "volume": None,
        "amount": 123.0,
    }])
    rows = task.post_process(FakeCtx(), {"000300.SH": frame})
    assert rows == [{
        "security_id": 7,
        "trade_date": "2026-07-27",
        "symbol": "000300",
        "open": 4000.0,
        "high": 4050.0,
        "low": 3980.0,
        "close": 4020.0,
        "volume": None,
        "amount": 123,
        "preclose": None,
        "pct_chg": None,
    }]


def test_security_registry_task_supports_documented_identity_families():
    assert {
        "stock", "index", "etf", "cb", "hk_connect", "repo", "futures", "option",
    } <= set(SECURITY_TYPE_SPECS)
    frame = pd.DataFrame(
        [{"symbol": "上证指数"}],
        index=pd.Index(["000001.SH"], name="code"),
    )
    rows = StockZHAList._rows_from_code_info(
        frame,
        SECURITY_TYPE_SPECS["index"],
        "ALL",
    )
    assert rows == [{
        "symbol": "000001",
        "name": "上证指数",
        "exchange": "SH",
        "asset_type": "index",
        "market": "zh_a",
        "status": "active",
    }]


def test_security_registry_task_only_upserts_changed_identities():
    downloaded = [
        {
            "symbol": "000001", "name": "上证指数", "exchange": "SH",
            "asset_type": "index", "market": "zh_a", "status": "active",
        },
        {
            "symbol": "000300", "name": "沪深300", "exchange": "SH",
            "asset_type": "index", "market": "zh_a", "status": "active",
        },
    ]
    existing = {
        ("index", "zh_a"): {
            ("SH", "000001"): {
                "symbol": "000001", "name": "上证指数", "exchange": "SH",
                "asset_type": "index", "market": "zh_a", "status": "active",
            },
        },
    }
    assert StockZHAList._changed_rows(downloaded, existing) == [downloaded[1]]


def test_index_zh_a_has_no_code_default_and_uses_registry_watermarks():
    class Phoenix:
        def get_securities(self, **_kwargs):
            return {
                11: {
                    "security_id": 11, "symbol": "000001",
                    "exchange": "SH", "asset_type": "index", "market": "zh_a",
                },
            }

        def get_bars_last_update(self, **_kwargs):
            return {11: "2026-07-27"}

    task = IndexZhADaily()
    assert task._index_codes({}) == []
    ctx = FakeCtx({
        "indexes": ["000001.SH"],
        "start_date": "2026-07-01",
    })
    ctx.dept_http = {DeptServices.PHOENIXA: Phoenix()}
    task.load_dynamic_parameters(ctx)
    assert ctx.params["effective_start_dates"] == {
        "000001.SH": "2026-07-28",
    }
    assert ctx.params["pending_index_codes"] == ["000001.SH"]
    assert task._security_by_code["000001.SH"]["security_id"] == 11


def test_index_zh_a_noop_watermark_skips_market_client():
    class Phoenix:
        def get_securities(self, **_kwargs):
            return {
                11: {
                    "security_id": 11, "symbol": "000001",
                    "exchange": "SH", "asset_type": "index", "market": "zh_a",
                },
            }

        def get_bars_last_update(self, **_kwargs):
            return {11: "2026-07-28"}

    task = IndexZhADaily()
    ctx = FakeCtx({
        "indexes": ["000001.SH"],
        "start_date": "2026-07-01",
        "end_date": "2026-07-28",
    })
    ctx.dept_http = {DeptServices.PHOENIXA: Phoenix()}
    task.load_dynamic_parameters(ctx)
    assert ctx.params["pending_index_codes"] == []
    task.before_execute(ctx)
    assert not hasattr(task, "_market_data")
    assert task.execute(ctx) == {}


def test_cn_margin_summary_skips_missing_without_zero_fill():
    task = StockZhAMarginSummary()
    frame = pd.DataFrame([{
        "TRADE_DATE": "2026-07-27",
        "SUM_BORROW_MONEY_BALANCE": 10.0,
        "SUM_PURCH_WITH_BORROW_MONEY": None,
    }])
    rows = task.post_process(FakeCtx({
        "effective_start_date": "2026-07-27",
        "end_date": "2026-07-27",
    }), frame)
    assert rows == [{
        "trade_date": "2026-07-27",
        "financing_balance": 10.0,
    }]


def test_cn_margin_summary_aggregates_source_market_rows_per_date():
    task = StockZhAMarginSummary()
    frame = pd.DataFrame([
        {
            "TRADE_DATE": "2026-07-27",
            "SUM_BORROW_MONEY_BALANCE": 10.0,
            "SUM_PURCH_WITH_BORROW_MONEY": 2.0,
        },
        {
            "TRADE_DATE": "2026-07-27",
            "SUM_BORROW_MONEY_BALANCE": 20.0,
            "SUM_PURCH_WITH_BORROW_MONEY": None,
        },
    ])
    rows = task.post_process(FakeCtx({
        "effective_start_date": "2026-07-27",
        "end_date": "2026-07-27",
    }), frame)
    assert rows == [{
        "trade_date": "2026-07-27",
        "financing_balance": 30.0,
        "financing_buy": 2.0,
    }]


def test_hsgt_keeps_symbol_and_only_rows_after_its_watermark():
    task = StockZhAHsgtHist()
    frame = pd.DataFrame([
        {"日期": "2026-07-26", "当日成交净买额": 1},
        {
            "日期": "2026-07-27",
            "当日成交净买额": 2,
            "买入成交额": 3,
            "沪深300": 4500,
            "领涨股": "测试股票",
            "领涨股-代码": "600000.SH",
        },
    ])
    ctx = FakeCtx({
        "symbols": ["北向资金"],
        "effective_start_dates": {"北向资金": "2026-07-27"},
        "end_date": "2026-07-27",
    })
    rows = task.post_process(ctx, {"北向资金": frame})
    assert rows == [{
        "symbol": "北向资金",
        "trade_date": "2026-07-27",
        "net_buy": 2.0,
        "buy_amount": 3.0,
        "benchmark_value": 4500.0,
        "leading_stock_name": "测试股票",
        "leading_stock_symbol": "600000.SH",
    }]


def test_qvix_keeps_real_ohlc_and_filters_per_symbol_watermark():
    task = IndexZhAOptionQVIX()
    frame = pd.DataFrame([
        {"date": "2026-07-26", "open": 10, "high": 12, "low": 9, "close": 11},
        {"date": "2026-07-27", "open": 11, "high": 13, "low": 10, "close": 12},
    ])
    ctx = FakeCtx({
        "symbols": ["500ETF"],
        "effective_start_dates": {"500ETF": "2026-07-27"},
        "end_date": "2026-07-27",
    })
    rows = task.post_process(ctx, {"500ETF": frame})
    assert rows == [{
        "symbol": "500ETF",
        "trade_date": "2026-07-27",
        "open": 11.0,
        "high": 13.0,
        "low": 10.0,
        "close": 12.0,
    }]


def test_option_daily_stats_supports_sse_and_szse_fields():
    task = OptionZhADailyStats()
    result = {
        ("SSE", "2026-07-27"): pd.DataFrame([{
            "合约标的代码": "510050",
            "合约标的名称": "上证50ETF",
            "合约数量": 120,
            "总成交额": 500,
            "总成交量": 1000,
            "认购成交量": 600,
            "认沽成交量": 400,
            "认沽/认购": 66.67,
            "未平仓合约总数": 2000,
            "未平仓认购合约数": 1200,
            "未平仓认沽合约数": 800,
            "交易日": "2026-07-27",
        }]),
        ("SZSE", "2026-07-27"): pd.DataFrame([{
            "合约标的代码": 159915,
            "合约标的名称": "创业板ETF",
            "成交量": 900,
            "认购成交量": 500,
            "认沽成交量": 400,
            "认沽/认购持仓比": 88.8,
            "未平仓合约总数": 1800,
            "未平仓认购合约数": 1000,
            "未平仓认沽合约数": 800,
            "交易日": "2026-07-27",
        }]),
    }
    rows = task.post_process(
        FakeCtx({"exchanges": ["SSE", "SZSE"]}),
        result,
    )
    assert rows[0]["exchange"] == "SSE"
    assert rows[0]["underlying_symbol"] == "510050"
    assert rows[0]["put_call_volume_ratio"] == 66.67
    assert rows[1]["exchange"] == "SZSE"
    assert rows[1]["underlying_symbol"] == "159915"
    assert rows[1]["volume"] == 900
    assert rows[1]["put_call_open_interest_ratio"] == 88.8


def test_option_daily_stats_resolves_registry_identity_before_sink():
    class Phoenix:
        def __init__(self):
            self.payload = None

        def get_securities(self, **kwargs):
            if kwargs["asset_type"] != "etf":
                return {}
            return {
                51: {
                    "security_id": 51,
                    "symbol": "510050",
                    "exchange": "SH",
                },
                159915: {
                    "security_id": 159915,
                    "symbol": "159915",
                    "exchange": "SZ",
                },
            }

        def upsert_option_daily_stats(self, *, rows, run_id):
            self.payload = rows
            return run_id == "risk-test"

    phoenix = Phoenix()
    ctx = FakeCtx()
    ctx.dept_http = {DeptServices.PHOENIXA: phoenix}
    OptionZhADailyStats().sink(ctx, [
        {
            "exchange": "SSE",
            "underlying_symbol": "510050",
            "trade_date": "2026-07-27",
        },
        {
            "exchange": "SZSE",
            "underlying_symbol": "159915",
            "trade_date": "2026-07-27",
        },
    ])
    assert phoenix.payload == [
        {
            "exchange": "SSE",
            "underlying_security_id": 51,
            "trade_date": "2026-07-27",
        },
        {
            "exchange": "SZSE",
            "underlying_security_id": 159915,
            "trade_date": "2026-07-27",
        },
    ]


def test_global_index_requires_real_ohlc():
    task = GlobalIndexDaily()
    result = {
        "SPX": {
            "spec": {
                "symbol": "SPX",
                "security_id": 17,
                "effective_start_date": "2026-07-27",
            },
            "frame": pd.DataFrame([
                {"日期": "2026-07-27", "今开": 1, "最高": 2, "最低": 0.5, "最新价": 1.5},
                {"日期": "2026-07-28", "今开": 1, "最高": 2, "最低": None, "最新价": 1.5},
            ]),
        },
    }
    rows = task.post_process(
        FakeCtx({"end_date": "2026-07-28"}),
        result,
    )
    assert len(rows) == 1
    assert rows[0]["security_id"] == 17
    assert rows[0]["asset_type"] == "index"


def test_global_index_has_no_code_default():
    assert configured_specs({}, "indexes") == []


def test_global_index_normalizes_hstech_ohlc():
    task = GlobalIndexDaily()
    result = {
        "HSTECH": {
            "spec": {
                "symbol": "HSTECH",
                "security_id": 19,
                "effective_start_date": "2026-07-27",
                "source_api": "stock_hk_index_daily_sina",
            },
            "frame": pd.DataFrame([{
                "date": "2026-07-27", "open": "5100.1", "high": 5200,
                "low": 5050, "close": 5180, "volume": 1234,
            }]),
        },
    }
    rows = task.post_process(
        FakeCtx({"end_date": "2026-07-27"}),
        result,
    )
    assert rows == [{
        "asset_type": "index",
        "security_id": 19,
        "trade_date": "2026-07-27",
        "open": 5100.1,
        "high": 5200.0,
        "low": 5050.0,
        "close": 5180.0,
        "volume": 1234,
        "amount": None,
        "preclose": None,
        "pct_chg": None,
    }]


def test_global_rate_persists_all_source_fields_vertically():
    task = GlobalRateDaily()
    selected = [
        spec for spec in RATE_SERIES
        if spec["symbol"] in {"CN_GOVT_5Y", "US_GDP_YOY"}
    ]
    pending = [
        {
            **spec,
            "security_id": index + 41,
            "effective_start_date": "2026-07-27",
        }
        for index, spec in enumerate(selected)
    ]
    frame = pd.DataFrame([{
        "日期": "2026-07-27",
        "中国国债收益率5年": 2.5,
        "美国GDP年增率": 3.1,
    }])
    rows = task.post_process(
        FakeCtx({
            "pending_series": pending,
            "end_date": "2026-07-27",
        }),
        frame,
    )
    assert [
        (row["security_id"], row["observation_type"], row["value"])
        for row in rows
    ] == [
        (41, "bond_yield", 2.5),
        (42, "gdp_yoy", 3.1),
    ]


def test_global_registry_normalizes_source_snapshots_and_deltas():
    task = GlobalSecurityList()
    rows = list(task._snapshot_rows(
        "index",
        pd.DataFrame([{"代码": "SPX", "名称": "标普500"}]),
    ))
    assert rows == [{
        "symbol": "SPX",
        "name": "标普500",
        "exchange": "US",
        "asset_type": "index",
        "market": "global",
        "status": "active",
    }]
    existing = {
        ("index", "global"): {
            ("US", "SPX"): rows[0],
        },
    }
    assert task._changed_rows(rows, existing) == []


def test_global_commodity_is_standard_futures_bar_not_wide_row():
    task = GlobalCommodityDaily()
    result = {
        "HG00Y": {
            "spec": {
                "symbol": "HG00Y",
                "security_id": 31,
                "effective_start_date": "2026-07-27",
            },
            "frame": pd.DataFrame([{
                "日期": "2026-07-27",
                "开盘": 4.1,
                "最高": 4.3,
                "最低": 4.0,
                "最新价": 4.2,
                "总量": 100,
                "涨幅": 1.2,
            }]),
        },
    }
    rows = task.post_process(
        FakeCtx({"end_date": "2026-07-27"}),
        result,
    )
    assert rows[0]["asset_type"] == "futures"
    assert rows[0]["security_id"] == 31
    assert "copper" not in rows[0]


def test_stock_us_list_and_daily_use_registry_identity():
    identity_rows = StockUSList().post_process(
        FakeCtx(),
        pd.DataFrame([{"代码": "105.NVDA", "名称": "NVIDIA"}]),
    )
    assert identity_rows == [{
        "symbol": "NVDA",
        "name": "NVIDIA",
        "exchange": "NASDAQ",
        "asset_type": "stock",
        "market": "us",
        "status": "active",
    }]

    task = StockUSDaily()
    result = {
        "NVDA": {
            "security": {
                "symbol": "NVDA",
                "security_id": 23,
                "effective_start_date": "2026-07-27",
            },
            "frame": pd.DataFrame([{
                "日期": "2026-07-27", "开盘": 100, "最高": 110, "最低": 98,
                "收盘": 108, "成交量": 1000, "成交额": None, "涨跌幅": 2.3,
            }]),
        },
    }
    rows = task.post_process(
        FakeCtx({"end_date": "2026-07-27"}),
        result,
    )
    assert rows[0]["security_id"] == 23
    assert rows[0]["amount"] is None
    assert rows[0]["volume"] == 1000


def test_notice_and_disclosure_schedule_resolve_security_ids():
    notice = StockZhANotice()
    notice._security_by_symbol = {"000001": {"security_id": 11}}
    notice_rows = notice.post_process(
        FakeCtx(),
        {"000001": pd.DataFrame([{
            "公告标题": "测试公告", "公告时间": "2026-07-27",
            "公告链接": "https://example.invalid/a", "简称": "平安银行",
        }])},
    )
    assert notice_rows[0]["security_id"] == 11

    schedule = StockZhADisclosureSchedule()
    schedule._security_by_symbol = {"000001": {"security_id": 11}}
    schedule_rows = schedule.post_process(
        FakeCtx(),
        {"2026半年报": pd.DataFrame([{
            "股票代码": "000001", "股票简称": "平安银行",
            "首次预约": "2026-08-20", "初次变更": None,
            "二次变更": None, "三次变更": None, "实际披露": None,
        }])},
    )
    assert schedule_rows[0]["event_date"] == "2026-08-20"
    assert schedule_rows[0]["title"] == "2026半年报披露计划"


def test_notice_filters_rows_before_each_security_watermark():
    task = StockZhANotice()
    task._security_by_symbol = {"000001": {"security_id": 11}}
    rows = task.post_process(
        FakeCtx({
            "effective_start_dates": {"000001": "2026-07-28"},
            "end_date": "2026-07-29",
        }),
        {"000001": pd.DataFrame([
            {"公告标题": "旧公告", "公告时间": "2026-07-27"},
            {"公告标题": "新公告", "公告时间": "2026-07-28"},
        ])},
    )
    assert [row["title"] for row in rows] == ["新公告"]


def test_disclosure_periods_are_derived_from_run_date():
    assert disclosure_periods({}, pd.Timestamp("2026-01-15")) == ["2025年报"]
    assert disclosure_periods({}, pd.Timestamp("2026-03-15")) == [
        "2025年报", "2026一季",
    ]
    assert disclosure_periods({}, pd.Timestamp("2026-07-15")) == ["2026半年报"]
    assert disclosure_periods({}, pd.Timestamp("2026-09-15")) == ["2026三季"]
    assert disclosure_periods(
        {"year": 2027, "report_types": ["一季", "半年报"]},
        pd.Timestamp("2026-09-15"),
    ) == ["2027一季", "2027半年报"]


def test_disclosure_schedule_skips_unchanged_existing_event():
    task = StockZhADisclosureSchedule()
    task._security_by_symbol = {"000001": {"security_id": 11}}
    frame = pd.DataFrame([{
        "股票代码": "000001", "股票简称": "平安银行",
        "首次预约": "2026-08-20", "初次变更": None,
        "二次变更": None, "三次变更": None, "实际披露": None,
    }])
    first = task.post_process(FakeCtx(), {"2026半年报": frame})
    row = first[0]
    task._existing_events = {
        (11, "2026-08-20", "2026半年报披露计划"):
            json.dumps(
                row["data_json"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
    }
    assert task.post_process(FakeCtx(), {"2026半年报": frame}) == []

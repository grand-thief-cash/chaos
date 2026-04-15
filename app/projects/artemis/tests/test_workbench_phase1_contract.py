from __future__ import annotations

from types import SimpleNamespace

import artemis.engines.task_engine  # noqa: F401

from artemis.models.workbench import WorkbenchRunReq, normalize_dimensions
from artemis.services.workbench.backtest import list_strategies, run_backtest
from artemis.services.workbench.market_data import get_market_bars


class FakePhoenixClient:
    def __init__(self):
        self.calls = []

    def get_bars(self, **kwargs):
        """模拟 PhoenixAClient.get_bars() — v2 provider 接口。"""
        self.calls.append(kwargs)
        return [
            {
                "date": "2024-01-02",
                "code": kwargs.get("symbol", ""),
                "open": 10.0,
                "high": 10.5,
                "low": 9.5,
                "close": 10.2,
                "volume": 1000,
                "amount": 100000,
            }
        ]


class FakeBroker:
    def get_cash(self):
        return 100000.0

    def get_value(self):
        return 105000.0


class FakeCerebro:
    def __init__(self):
        self.broker = FakeBroker()

    def run(self):
        return [SimpleNamespace()]


class FakeStrategySpec:
    code = "sma_cross"
    default_params = {"fast": 10, "slow": 30}
    supported_modes = ("historical",)
    supported_timeframes = ("daily",)
    param_schema = {"fast": {"type": "int", "min": 1}}

    def validate_params(self, params):
        return []


def test_normalize_dimensions_for_index_forces_nf():
    dims = normalize_dimensions(
        asset_type="index",
        market="zh_a",
        period="daily",
        adjust="",
    )
    assert dims.adjust == "nf"
    assert dims.period == "daily"


def test_get_market_bars_uses_period_internally_and_maps_to_phoenix_timeframe(monkeypatch):
    fake_client = FakePhoenixClient()

    monkeypatch.setattr(
        "artemis.services.workbench.market_data._build_phoenix_client",
        lambda source=None: fake_client,
    )

    result = get_market_bars(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-01-31",
        period="weekly",
        adjust="hfq",
        asset_type="stock",
        market="zh_a",
        source="production",
        use_cache=False,
    )

    assert result["period"] == "weekly"
    assert "timeframe" not in result
    # PhoenixBarsProvider.fetch_bars() 使用 v2 get_bars() 接口，传 period 而非 timeframe
    assert fake_client.calls[0]["period"] == "weekly"
    assert fake_client.calls[0]["adjust"] == "hfq"


def test_list_strategies_exposes_supported_periods_not_supported_timeframes(monkeypatch):
    monkeypatch.setattr(
        "artemis.services.workbench.backtest.strategy_registry._registry",
        {"sma_cross": FakeStrategySpec()},
    )

    result = list_strategies()

    assert result["strategies"][0]["supported_periods"] == ["daily"]
    assert "supported_timeframes" not in result["strategies"][0]


def test_run_backtest_uses_period_and_returns_period_summary(monkeypatch):
    captured_market_data_call = {}

    monkeypatch.setattr(
        "artemis.services.workbench.backtest.strategy_registry.require",
        lambda code: FakeStrategySpec(),
    )
    monkeypatch.setattr(
        "artemis.services.workbench.backtest.analyzer_profile_registry.require",
        lambda code: object(),
    )

    def fake_get_market_bars(**kwargs):
        captured_market_data_call.update(kwargs)
        return {
            "symbol": kwargs["symbol"],
            "period": kwargs["period"],
            "start_date": kwargs["start_date"],
            "end_date": kwargs["end_date"],
            "bars": [
                {
                    "date": "2024-01-02",
                    "code": kwargs["symbol"],
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.5,
                    "close": 10.2,
                    "volume": 1000,
                    "amount": 100000,
                }
            ],
        }

    monkeypatch.setattr(
        "artemis.services.workbench.market_data.get_market_bars",
        fake_get_market_bars,
    )
    monkeypatch.setattr(
        "artemis.services.workbench.backtest.get_market_bars",
        fake_get_market_bars,
        raising=False,
    )
    monkeypatch.setattr(
        "artemis.services.workbench.backtest.execute_backtest",
        lambda **kwargs: {
            "strategy_instance": SimpleNamespace(),
            "analyzer_results": {},
            "bars_processed": 1,
            "start_cash": 100000.0,
            "end_value": 105000.0,
        },
    )
    monkeypatch.setattr(
        "artemis.services.workbench.backtest.BacktestResultNormalizer.normalize",
        lambda **kwargs: {
            "run_meta": {"run_id": "wb-1", "parent_run_id": None, "task_code": "workbench"},
            "summary": {
                "strategy_code": kwargs["strategy_code"],
                "symbol": kwargs["symbol"],
                "period": kwargs["period"],
                "start_date": kwargs["start_date"],
                "end_date": kwargs["end_date"],
            },
            "artifacts": {},
        },
    )

    req = WorkbenchRunReq(
        strategy_code="sma_cross",
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-01-31",
        period="weekly",
        adjust="nf",
        asset_type="stock",
        market="zh_a",
        strategy_params={"fast": 5},
    )

    result = run_backtest(req)

    assert captured_market_data_call["period"] == "weekly"
    assert result["summary"]["period"] == "weekly"
    assert "timeframe" not in result["summary"]


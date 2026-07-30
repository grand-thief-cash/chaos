from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from artemis.models.t_trading import TBatchReplayRequest, TExecutionConfig, TReplayRequest, TStrategyConfig
from artemis.services.t_trading.features import build_causal_features
from artemis.services.t_trading.replay import run_replay_from_bars
from artemis.services.t_trading.signal_engine import generate_signals


def _bars() -> list[dict]:
    prices = [
        10.00, 10.02, 10.01, 10.03, 10.02, 10.01, 10.00, 9.99, 9.98, 9.97,
        9.90, 9.82, 9.74, 9.68, 9.62, 9.66, 9.72, 9.80, 9.90, 10.02,
        10.14, 10.25, 10.36, 10.43, 10.49, 10.44, 10.36, 10.29, 10.24, 10.20,
    ]
    start = datetime(2026, 7, 1, 9, 35, tzinfo=timezone(timedelta(hours=8)))
    result = []
    previous = prices[0]
    for index, close in enumerate(prices):
        opened = previous
        result.append(
            {
                "date": (start + timedelta(minutes=5 * index)).isoformat(),
                "open": opened,
                "high": max(opened, close) + 0.02,
                "low": min(opened, close) - 0.02,
                "close": close,
                "volume": 10000 + index * 100,
                "amount": close * (10000 + index * 100),
            }
        )
        previous = close
    return result


def _request() -> TReplayRequest:
    return TReplayRequest(
        security_id=1,
        trade_date=date(2026, 7, 1),
        strategy=TStrategyConfig(
            window=5,
            entry_z=0.5,
            exit_z=0.5,
            entry_rsi=50,
            exit_rsi=50,
            confirmation_bars=4,
            cooldown_bars=0,
            max_round_trips=2,
        ),
        execution=TExecutionConfig(quantity=100, slippage_bps=1),
    )


def test_replay_is_ephemeral_and_fills_on_next_bar():
    result = run_replay_from_bars(_request(), _bars(), symbol="sh.600000")
    assert result["run_meta"]["persistence_mode"] == "ephemeral"
    assert result["run_meta"]["causality"] == "decision_at_bar_close_fill_at_next_bar_open"
    assert result["signals"]
    assert len(result["signals"]) == len(result["fills"])
    for signal, fill in zip(result["signals"], result["fills"]):
        assert fill["bar_index"] == signal["bar_index"] + 1
        assert fill["fill_time"] > signal["decision_time"]


def test_signal_prefix_invariance_proves_no_future_dependency():
    request = _request()
    bars = _bars()
    full_frame = build_causal_features(bars, request.strategy.window)
    full_signals = generate_signals(full_frame, request.strategy)
    assert full_signals
    first = full_signals[0]
    prefix = bars[: first["bar_index"] + 2]
    prefix_frame = build_causal_features(prefix, request.strategy.window)
    prefix_signals = generate_signals(prefix_frame, request.strategy)
    assert prefix_signals[0]["decision_time"] == first["decision_time"]
    assert prefix_signals[0]["side"] == first["side"]


def test_costs_are_included_in_round_trip_net_pnl():
    result = run_replay_from_bars(_request(), _bars())
    assert result["round_trips"]
    for trip in result["round_trips"]:
        assert trip["net_pnl"] == round(trip["gross_pnl"] - trip["total_fee"], 4)


def test_batch_isolates_item_failure_and_omits_large_details(monkeypatch):
    from artemis.services.t_trading import replay as replay_module

    def fake_run(request):
        if request.security_id == 2:
            raise RuntimeError("upstream unavailable")
        return run_replay_from_bars(request, _bars(), symbol="sh.600000")

    monkeypatch.setattr(replay_module, "run_replay", fake_run)
    request = TBatchReplayRequest(
        security_ids=[1, 2],
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 1),
        strategy=_request().strategy,
        execution=_request().execution,
    )
    result = replay_module.run_batch_replay(request)

    assert result["summary"]["replay_days"] == 1
    assert result["failures"][0]["security_id"] == 2
    assert result["by_day"][0]["trade_date"] == "2026-07-01"
    assert "bars" not in result["results"][0]

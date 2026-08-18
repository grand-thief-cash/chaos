from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from artemis.models.t_trading import (
    TBatchReplayRequest,
    TExecutionConfig,
    TReplayRequest,
    TSignalEvaluationConfig,
    TStrategyConfig,
)
from artemis.services.t_trading.features import build_causal_features
from artemis.services.t_trading.replay import (
    _intraday_session_bounds,
    run_replay_from_bars,
)
from artemis.services.t_trading.signal_evaluation import evaluate_signals
from artemis.services.t_trading.signal_engine import generate_signals


def test_intraday_session_bounds_cover_auction_to_close_only():
    start, end = _intraday_session_bounds(date(2026, 7, 1))

    assert start == "2026-07-01T09:15:00+08:00"
    assert end == "2026-07-01T15:00:59.999999+08:00"


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


def test_replay_is_ephemeral_and_signal_evaluation_is_primary():
    result = run_replay_from_bars(_request(), _bars(), symbol="sh.600000")
    assert result["run_meta"]["persistence_mode"] == "ephemeral"
    assert (
        result["run_meta"]["causality"]
        == "signal_at_bar_close_evaluate_subsequent_bars"
    )
    assert result["run_meta"]["execution_simulation"] == "disabled"
    assert result["signals"]
    assert result["fills"] == []
    assert result["round_trips"] == []
    assert result["execution_summary"]["enabled"] is False
    assert result["signal_evaluation"]["evaluation_kind"] == "forward_event_study_v1"
    assert result["summary"] == result["signal_evaluation"]["summary"]
    assert result["summary"]["horizon_bars"] == 6
    assert result["signal_evaluation"]["outcomes"]
    assert result["indicator_sets"][0]["strategy"] == (
        "causal_mean_reversion_v1"
    )
    assert len(result["indicator_sets"][0]["points"]) == len(result["bars"])


def test_prior_session_warmup_seeds_opening_indicators_but_resets_vwap():
    target = _bars()[:5]
    warmup = []
    for day_offset in (2, 1):
        for bar in _bars():
            item = dict(bar)
            item["date"] = (
                pd.Timestamp(bar["date"]) - pd.Timedelta(days=day_offset)
            ).isoformat()
            warmup.append(item)

    result = run_replay_from_bars(
        _request(),
        target,
        context_bars={"warmup_bars": warmup},
    )
    first = result["indicator_sets"][0]["points"][0]

    assert first["ema_fast"] is not None
    assert first["macd"] is not None
    assert first["macd_signal"] is not None
    assert first["rsi"] is not None
    assert first["vwap"] == target[0]["close"]
    assert len(result["bars"]) == len(target)


def test_signal_prefix_invariance_proves_no_future_dependency():
    request = _request()
    bars = _bars()
    full_frame = build_causal_features(bars, request.strategy.window)
    full_signals = generate_signals(full_frame, request.strategy)
    assert full_signals
    first = full_signals[0]
    prefix = bars[: first["bar_index"] + 1]
    prefix_frame = build_causal_features(prefix, request.strategy.window)
    prefix_signals = generate_signals(prefix_frame, request.strategy)
    assert prefix_signals[0]["decision_time"] == first["decision_time"]
    assert prefix_signals[0]["side"] == first["side"]


def test_macd_reversion_signals_stay_on_the_correct_ema_side():
    config = TStrategyConfig(
        strategy="macd_volume_momentum_v1",
        direction="independent",
        window=5,
        ema_fast=3,
        ema_slow=6,
        macd_signal=2,
        atr_window=5,
        ema_deviation_atr=0.05,
        macd_turn_bars=1,
        min_volume_ratio=0.5,
        volume_confirmation_window=1,
        confirmation_bars=1,
        cooldown_bars=0,
        max_round_trips=3,
    )
    base_time = datetime(2026, 7, 1, 9, 35, tzinfo=timezone.utc)
    frame = pd.DataFrame(
        [
            {
                "date": base_time,
                "open": 9.0,
                "close": 9.0,
                "prev_close": None,
                "rsi": 25.0,
                "prev_rsi": None,
                "macd_hist": -0.2,
                "prev_macd_hist": -0.3,
                "macd_hist_delta": 0.1,
                "macd_hist_rising_bars": 1,
                "macd_hist_falling_bars": 0,
                "ema_slow": 10.0,
                "ema_deviation_atr": -1.0,
                "recent_volume_ratio_max": 2.0,
                "atr": 0.2,
            },
            {
                "date": base_time + timedelta(minutes=1),
                "open": 8.9,
                "close": 9.0,
                "prev_close": 8.95,
                "rsi": 30.0,
                "prev_rsi": 25.0,
                "macd_hist": -0.1,
                "prev_macd_hist": -0.2,
                "macd_hist_delta": 0.1,
                "macd_hist_rising_bars": 2,
                "macd_hist_falling_bars": 0,
                "ema_slow": 10.0,
                "ema_deviation_atr": -1.0,
                "recent_volume_ratio_max": 2.0,
                "atr": 0.2,
            },
            {
                "date": base_time + timedelta(minutes=2),
                "open": 11.1,
                "close": 11.0,
                "prev_close": 11.05,
                "rsi": 70.0,
                "prev_rsi": 75.0,
                "macd_hist": 0.1,
                "prev_macd_hist": 0.2,
                "macd_hist_delta": -0.1,
                "macd_hist_rising_bars": 0,
                "macd_hist_falling_bars": 2,
                "ema_slow": 10.0,
                "ema_deviation_atr": 1.0,
                "recent_volume_ratio_max": 2.0,
                "atr": 0.2,
            },
        ]
    )
    signals = generate_signals(frame, config)

    assert {signal["side"] for signal in signals} == {"BUY", "SELL"}
    for signal in signals:
        deviation = signal["features"]["ema_deviation_atr"]
        if signal["side"] == "BUY":
            assert deviation <= -config.ema_deviation_atr
        else:
            assert deviation >= config.ema_deviation_atr
    first = signals[0]
    prefix_frame = frame.iloc[: first["bar_index"] + 1].copy()
    prefix_signals = generate_signals(prefix_frame, config)
    assert prefix_signals[0]["decision_time"] == first["decision_time"]
    assert prefix_signals[0]["side"] == first["side"]


def test_regime_reversal_blocks_weak_buy_and_accepts_three_of_four():
    config = TStrategyConfig(
        strategy="macd_volume_regime_reversal_v1",
        direction="independent",
        window=5,
        ema_fast=3,
        ema_slow=6,
        macd_signal=2,
        atr_window=5,
        ema_deviation_atr=0.35,
        macd_turn_bars=1,
        min_volume_ratio=0.5,
        volume_confirmation_window=1,
        confirmation_bars=1,
        cooldown_bars=0,
        max_round_trips=1,
        deep_reversal_min_score=3,
    )
    base_time = datetime(2026, 7, 1, 9, 35, tzinfo=timezone.utc)
    rows = [
        {
            "date": base_time,
            "open": 9.0,
            "close": 9.0,
            "prev_close": None,
            "rsi": 25.0,
            "prev_rsi": None,
            "macd_hist": -0.2,
            "prev_macd_hist": -0.3,
            "macd_hist_delta": 0.1,
            "macd_hist_rising_bars": 1,
            "macd_hist_falling_bars": 0,
            "ema_slow": 10.0,
            "vwap": 9.5,
            "ema_deviation_atr": -1.0,
            "recent_min_ema_deviation_atr": -1.0,
            "recent_max_ema_deviation_atr": -0.5,
            "recent_volume_ratio_max": 2.0,
            "bearish_regime": 1.0,
            "bullish_regime": 0.0,
            "bullish_reversal_evidence_score": 2.0,
            "bearish_reversal_evidence_score": 0.0,
            "atr": 0.2,
        },
        {
            "date": base_time + timedelta(minutes=1),
            "open": 8.9,
            "close": 9.0,
            "prev_close": 8.8,
            "rsi": 30.0,
            "prev_rsi": 25.0,
            "macd_hist": -0.1,
            "prev_macd_hist": -0.2,
            "macd_hist_delta": 0.1,
            "macd_hist_rising_bars": 2,
            "macd_hist_falling_bars": 0,
            "ema_slow": 10.0,
            "vwap": 9.5,
            "ema_deviation_atr": -1.0,
            "recent_min_ema_deviation_atr": -1.0,
            "recent_max_ema_deviation_atr": -0.5,
            "recent_volume_ratio_max": 2.0,
            "bearish_regime": 1.0,
            "bullish_regime": 0.0,
            "bullish_reversal_evidence_score": 2.0,
            "bearish_reversal_evidence_score": 0.0,
            "atr": 0.2,
        },
    ]
    weak = pd.DataFrame(rows)
    assert generate_signals(weak, config) == []

    strong = weak.copy()
    strong.loc[1, "bullish_reversal_evidence_score"] = 3.0
    signals = generate_signals(strong, config)

    assert len(signals) == 1
    assert signals[0]["side"] == "BUY"
    assert "adverse_regime_reversal_gate_passed" in signals[0][
        "reason_codes"
    ]
    assert "reversal_evidence_3_of_4" in signals[0]["reason_codes"]


def test_regime_reversal_sell_uses_downtrend_rebound_not_buy_mirror():
    config = TStrategyConfig(
        strategy="macd_volume_regime_reversal_v1",
        direction="independent",
        min_volume_ratio=0.8,
        macd_turn_bars=2,
        rebound_ema_tolerance_atr=0.5,
        minimum_recent_range=0.005,
        confirmation_bars=1,
        cooldown_bars=0,
        max_round_trips=1,
    )
    base_time = datetime(2026, 7, 1, 10, 5, tzinfo=timezone.utc)
    base = {
        "date": base_time,
        "open": 9.95,
        "close": 9.95,
        "prev_close": None,
        "rsi": 45.0,
        "prev_rsi": None,
        "vwap": 10.1,
        "ema_deviation_atr": 0.1,
        "macd_hist": 0.05,
        "macd_hist_delta": 0.01,
        "prev_macd_hist_delta": 0.01,
        "macd_hist_falling_bars": 0,
        "recent_volume_ratio_max": 1.2,
        "medium_return_fast": -0.006,
        "medium_return_slow": -0.012,
        "medium_recent_range": 0.008,
        "atr": 0.1,
    }
    rollover = {
        **base,
        "date": base_time + timedelta(minutes=1),
        "open": 9.96,
        "close": 9.93,
        "prev_close": 9.95,
        "rsi": 43.0,
        "prev_rsi": 45.0,
        "macd_hist": 0.04,
        "macd_hist_delta": -0.01,
        "prev_macd_hist_delta": 0.01,
    }

    signals = generate_signals(pd.DataFrame([base, rollover]), config)

    assert len(signals) == 1
    assert signals[0]["side"] == "SELL"
    assert "medium_downtrend_15_30" in signals[0]["reason_codes"]
    assert "macd_rebound_rolled_over" in signals[0]["reason_codes"]

    quiet = rollover.copy()
    quiet["medium_recent_range"] = 0.004
    assert generate_signals(pd.DataFrame([base, quiet]), config) == []


def test_intraday_reversal_features_are_prefix_invariant():
    bars = _bars()
    kwargs = {
        "panic_window_bars": 4,
        "panic_return_threshold": 0.01,
        "panic_volume_ratio": 1.2,
        "macd_divergence_lookback": 6,
        "rebound_confirmation_bars": 2,
        "rebound_recovery_ratio": 0.5,
        "regime_slope_bars": 3,
    }
    full = build_causal_features(bars, 5, **kwargs)
    prefix = build_causal_features(bars[:20], 5, **kwargs)
    fields = (
        "recent_bearish_shock",
        "recent_panic_volume_ratio_max",
        "bullish_divergence_recent",
        "bullish_rebound_structure",
        "bullish_reversal_evidence_score",
        "bearish_regime",
        "medium_return_fast",
        "medium_return_slow",
        "medium_recent_range",
    )
    for field in fields:
        full_value = full.iloc[19][field]
        prefix_value = prefix.iloc[-1][field]
        if pd.isna(full_value):
            assert pd.isna(prefix_value)
        else:
            assert prefix_value == full_value


def test_signal_engine_does_not_drop_last_bar_for_execution_convenience():
    config = TStrategyConfig(window=5, confirmation_bars=1)
    frame = pd.DataFrame(
        [
            {
                "date": datetime(2026, 7, 1, 9, 35, tzinfo=timezone.utc),
                "open": 9.0,
                "close": 9.0,
                "zscore": 0.0,
                "rsi": 50.0,
                "vwap": 9.0,
                "vwap_deviation": 0.0,
                "prev_close": None,
                "prev_rsi": None,
            },
            {
                "date": datetime(2026, 7, 1, 9, 40, tzinfo=timezone.utc),
                "open": 8.8,
                "close": 9.0,
                "zscore": -2.0,
                "rsi": 30.0,
                "vwap": 9.1,
                "vwap_deviation": -0.011,
                "prev_close": 8.9,
                "prev_rsi": 25.0,
            },
        ]
    )

    signals = generate_signals(frame, config)

    assert len(signals) == 1
    assert signals[0]["bar_index"] == 1


def test_execution_simulation_is_opt_in_and_kept_out_of_signal_summary():
    request = _request().model_copy(update={"include_execution_simulation": True})
    result = run_replay_from_bars(request, _bars())
    assert result["round_trips"]
    assert result["execution_summary"]["enabled"] is True
    for trip in result["round_trips"]:
        assert trip["net_pnl"] == round(trip["gross_pnl"] - trip["total_fee"], 4)
    assert "net_pnl" not in result["summary"]


def test_forward_event_study_scores_buy_and_sell_symmetrically():
    frame = build_causal_features(_bars(), 5)
    signals = [
        {
            "signal_id": "buy-low",
            "bar_index": 14,
            "decision_time": frame.iloc[14]["date"].isoformat(),
            "decision_price": float(frame.iloc[14]["close"]),
            "side": "BUY",
            "strategy": "test",
        },
        {
            "signal_id": "sell-high",
            "bar_index": 24,
            "decision_time": frame.iloc[24]["date"].isoformat(),
            "decision_price": float(frame.iloc[24]["close"]),
            "side": "SELL",
            "strategy": "test",
        },
    ]
    evaluation = evaluate_signals(
        frame,
        signals,
        TSignalEvaluationConfig(
            horizons_bars=[1, 3],
            primary_horizon_bars=3,
            target_return=0.003,
            stop_return=0.003,
        ),
    )

    horizon_three = [
        outcome
        for outcome in evaluation["outcomes"]
        if outcome["horizon_bars"] == 3
    ]
    assert all(outcome["direction_correct"] for outcome in horizon_three)
    assert all(outcome["directional_return"] > 0 for outcome in horizon_three)
    assert evaluation["summary"]["directional_accuracy"] == 1.0
    assert evaluation["summary"]["mean_mfe"] > evaluation["summary"]["mean_mae"]


def test_excursions_are_non_negative_and_exclude_decision_bar():
    bars = [
        {
            "date": datetime(2026, 7, 1, 9, 35, tzinfo=timezone.utc),
            "open": 10.0,
            "high": 10.2,
            "low": 9.9,
            "close": 10.0,
            "volume": 100,
            "amount": 1000,
        },
        {
            "date": datetime(2026, 7, 1, 9, 40, tzinfo=timezone.utc),
            "open": 9.8,
            "high": 9.9,
            "low": 9.5,
            "close": 9.6,
            "volume": 100,
            "amount": 960,
        },
    ]
    frame = build_causal_features(bars, 5)
    evaluation = evaluate_signals(
        frame,
        [
            {
                "signal_id": "buy-adverse-only",
                "bar_index": 0,
                "decision_time": frame.iloc[0]["date"].isoformat(),
                "decision_price": 10.0,
                "side": "BUY",
                "strategy": "test",
            }
        ],
        TSignalEvaluationConfig(
            horizons_bars=[1],
            primary_horizon_bars=1,
        ),
    )

    outcome = evaluation["outcomes"][0]
    assert outcome["mfe"] == 0.0
    assert outcome["mae"] == 0.05


def test_strategy_summary_keeps_selected_strategy_with_zero_signals():
    frame = build_causal_features(_bars(), 5)
    evaluation = evaluate_signals(
        frame,
        [],
        TSignalEvaluationConfig(),
        strategies=["multi_timeframe_pullback_v1"],
    )

    assert evaluation["by_strategy"] == [
        {
            **evaluation["summary"],
            "strategy": "multi_timeframe_pullback_v1",
        }
    ]


def test_all_ohlcv_strategy_variants_generate_auditable_signals():
    configs = [
        TStrategyConfig(
            strategy="macd_volume_momentum_v1",
            window=5,
            ema_fast=3,
            ema_slow=6,
            macd_signal=2,
            atr_window=5,
            min_volume_ratio=0.5,
            ema_deviation_atr=0.0,
            macd_turn_bars=1,
            volume_confirmation_window=1,
            confirmation_bars=4,
            cooldown_bars=0,
        ),
        TStrategyConfig(
            strategy="vwap_bollinger_reversion_v1",
            window=5,
            ema_fast=3,
            ema_slow=6,
            macd_signal=2,
            atr_window=5,
            bollinger_z=0.5,
            min_volume_ratio=0.5,
            max_trend_strength_atr=10,
            reversal_wick_ratio=0.1,
            entry_rsi=50,
            exit_rsi=50,
            confirmation_bars=4,
            cooldown_bars=0,
        ),
        TStrategyConfig(
            strategy="opening_range_breakout_v1",
            window=5,
            ema_fast=3,
            ema_slow=6,
            macd_signal=2,
            atr_window=5,
            opening_range_bars=4,
            breakout_atr_buffer=0,
            min_volume_ratio=0.5,
            confirmation_bars=4,
            cooldown_bars=0,
        ),
    ]
    for config in configs:
        frame = build_causal_features(
            _bars(),
            config.window,
            ema_fast=config.ema_fast,
            ema_slow=config.ema_slow,
            macd_signal=config.macd_signal,
            atr_window=config.atr_window,
            opening_range_bars=config.opening_range_bars,
            volume_confirmation_window=config.volume_confirmation_window,
        )
        signals = generate_signals(frame, config)
        assert signals, config.strategy
        assert {signal["strategy"] for signal in signals} == {config.strategy}
        assert {signal["confidence_kind"] for signal in signals} == {
            "rule_score_v2"
        }
        first = signals[0]
        prefix = frame.iloc[: first["bar_index"] + 1].copy()
        prefix_signals = generate_signals(prefix, config)
        assert prefix_signals[0]["decision_time"] == first["decision_time"]


def test_context_strategies_run_together_with_independent_signal_ids():
    bars = _bars()
    history = []
    for day_offset in range(1, 25):
        for bar in bars:
            item = dict(bar)
            item["date"] = (
                pd.Timestamp(bar["date"]) - pd.Timedelta(days=day_offset)
            ).isoformat()
            item["volume"] = 200
            history.append(item)

    benchmark = []
    benchmark_close = 100.0
    benchmark_moves = [0.001, -0.0006, 0.0003, -0.0002, 0.0008]
    for index, bar in enumerate(bars):
        benchmark_close *= 1 + benchmark_moves[index % len(benchmark_moves)]
        benchmark.append(
            {
                **bar,
                "open": benchmark_close,
                "high": benchmark_close * 1.001,
                "low": benchmark_close * 0.999,
                "close": benchmark_close,
            }
        )

    daily = []
    daily_start = pd.Timestamp("2026-05-01", tz="Asia/Shanghai")
    for index in range(50):
        price = 8 + index * 0.05
        daily.append(
            {
                "date": (daily_start + pd.Timedelta(days=index)).isoformat(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1000,
            }
        )
    higher = []
    higher_start = pd.Timestamp(
        "2026-06-30 09:30", tz="Asia/Shanghai"
    )
    for index in range(60):
        price = 9 + index * 0.03
        higher.append(
            {
                "date": (
                    higher_start + pd.Timedelta(minutes=30 * index)
                ).isoformat(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1000,
            }
        )

    common = {
        "window": 5,
        "ema_fast": 3,
        "ema_slow": 6,
        "macd_signal": 2,
        "atr_window": 5,
        "confirmation_bars": 4,
        "cooldown_bars": 0,
    }
    strategies = [
        TStrategyConfig(
            strategy="time_of_day_volume_momentum_v1",
            relative_volume_tod_threshold=0.5,
            min_time_of_day_history_days=20,
            **common,
        ),
        TStrategyConfig(
            strategy="market_residual_reversal_v1",
            market_beta_window=5,
            residual_z_threshold=0.25,
            **common,
        ),
        TStrategyConfig(
            strategy="multi_timeframe_pullback_v1",
            higher_ema_fast=3,
            higher_ema_slow=5,
            daily_trend_window=5,
            pullback_tolerance_atr=5,
            **common,
        ),
    ]
    request = TReplayRequest(
        security_id=1,
        trade_date=date(2026, 7, 1),
        period="min5",
        strategies=strategies,
        benchmark_security_id=2,
    )

    result = run_replay_from_bars(
        request,
        bars,
        context_bars={
            "historical_bars": history,
            "benchmark_bars": benchmark,
            "daily_bars": daily,
            "higher_timeframe_bars": higher,
        },
    )

    assert {signal["strategy"] for signal in result["signals"]} == {
        strategy.strategy for strategy in strategies
    }
    assert len({signal["signal_id"] for signal in result["signals"]}) == len(
        result["signals"]
    )
    assert result["run_meta"]["strategies"] == [
        strategy.strategy for strategy in strategies
    ]
    assert {
        row["strategy"] for row in result["signal_evaluation"]["by_strategy"]
    } == {strategy.strategy for strategy in strategies}
    features_by_strategy = {
        signal["strategy"]: signal["features"] for signal in result["signals"]
    }
    assert (
        features_by_strategy["time_of_day_volume_momentum_v1"][
            "relative_volume_tod"
        ]
        is not None
    )
    assert (
        features_by_strategy["market_residual_reversal_v1"][
            "market_residual_zscore"
        ]
        is not None
    )
    assert (
        features_by_strategy["multi_timeframe_pullback_v1"][
            "higher_timeframe_trend"
        ]
        == 1.0
    )


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
    assert result["summary"]["horizon_bars"] == 6
    assert result["failures"][0]["security_id"] == 2
    assert result["by_day"][0]["trade_date"] == "2026-07-01"
    assert result["by_strategy"][0]["strategy"] == (
        "causal_mean_reversion_v1"
    )
    assert "bars" not in result["results"][0]

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from artemis.services.t_trading.live_quotes import (
    OnlineSignalOutcomeTracker,
    QuotePoint,
)


SHANGHAI = timezone(timedelta(hours=8))


def _time(second: int) -> datetime:
    return datetime(2026, 7, 30, 9, 30, second, tzinfo=SHANGHAI)


def test_online_tracker_keeps_compact_buy_outcomes_without_raw_quotes():
    tracker = OnlineSignalOutcomeTracker(
        horizons_seconds=[10, 20],
        target_return=0.005,
        stop_return=0.003,
    )
    tracker.register(
        signal_id="live-buy-1",
        side="BUY",
        decision_time=_time(0),
        decision_price=10.0,
        strategy="macd_volume_momentum_v1",
    )

    assert tracker.update(QuotePoint(_time(5), 9.98)) == []
    first = tracker.update(QuotePoint(_time(10), 10.06))
    assert len(first) == 1
    assert first[0]["horizon_seconds"] == 10
    assert first[0]["directional_return"] == 0.006
    assert first[0]["mfe"] == 0.006
    assert first[0]["mae"] == 0.002
    assert first[0]["first_touch"] == "target_first"

    assert tracker.update(QuotePoint(_time(15), 10.08)) == []
    second = tracker.update(QuotePoint(_time(20), 10.04))
    assert second[0]["horizon_seconds"] == 20
    assert second[0]["mfe"] == 0.008
    assert second[0]["direction_correct"] is True
    assert tracker.active_signal_count == 0


def test_online_tracker_scores_sell_direction_symmetrically():
    tracker = OnlineSignalOutcomeTracker(
        horizons_seconds=[10],
        target_return=0.005,
        stop_return=0.003,
    )
    tracker.register(
        signal_id="live-sell-1",
        side="SELL",
        decision_time=_time(0),
        decision_price=10.0,
        strategy="opening_range_breakout_v1",
    )
    tracker.update(QuotePoint(_time(5), 10.02))
    outcomes = tracker.update(QuotePoint(_time(10), 9.94))

    assert outcomes[0]["directional_return"] == 0.006
    assert outcomes[0]["mfe"] == 0.006
    assert outcomes[0]["mae"] == 0.002
    assert outcomes[0]["first_touch"] == "target_first"


def test_online_tracker_rejects_duplicate_or_out_of_order_quotes():
    tracker = OnlineSignalOutcomeTracker(
        horizons_seconds=[10],
        target_return=0.005,
        stop_return=0.003,
    )
    tracker.update(QuotePoint(_time(5), 10.0))

    try:
        tracker.update(QuotePoint(_time(5), 10.01))
        raise AssertionError("duplicate quote should have been rejected")
    except ValueError as exc:
        assert "strictly increasing" in str(exc)

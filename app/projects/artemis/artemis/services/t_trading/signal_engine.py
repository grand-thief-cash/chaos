from __future__ import annotations

from typing import Any

import pandas as pd

from artemis.models.t_trading import TStrategyConfig
from artemis.services.t_trading.features import feature_snapshot


def _present(row: pd.Series, *fields: str) -> bool:
    return all(field in row and not pd.isna(row[field]) for field in fields)


def _mean_reversion_entry(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(row, "zscore", "rsi", "vwap"):
        return False
    if side == "BUY":
        return bool(
            row["zscore"] <= -config.entry_z
            and row["rsi"] <= config.entry_rsi
            and row["close"] <= row["vwap"]
        )
    return bool(
        row["zscore"] >= config.entry_z
        and row["rsi"] >= config.exit_rsi
        and row["close"] >= row["vwap"]
    )


def _mean_reversion_exit(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(row, "zscore", "rsi", "vwap"):
        return False
    if side == "SELL":
        return bool(
            (row["zscore"] >= config.exit_z or row["rsi"] >= config.exit_rsi)
            and row["close"] >= row["vwap"]
        )
    return bool(
        (row["zscore"] <= -config.exit_z or row["rsi"] <= config.entry_rsi)
        and row["close"] <= row["vwap"]
    )


def _macd_volume_entry(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(
        row,
        "macd_hist",
        "prev_macd_hist",
        "ema_fast",
        "ema_slow",
        "volume_ratio",
    ):
        return False
    if side == "BUY":
        return bool(
            row["macd_hist"] > row["prev_macd_hist"]
            and row["close"] >= row["ema_fast"] * 0.998
            and row["ema_fast"] >= row["ema_slow"]
            and row["volume_ratio"] >= config.min_volume_ratio
        )
    return bool(
        row["macd_hist"] < row["prev_macd_hist"]
        and row["close"] <= row["ema_fast"] * 1.002
        and row["ema_fast"] <= row["ema_slow"]
        and row["volume_ratio"] >= config.min_volume_ratio
    )


def _macd_volume_exit(
    row: pd.Series, side: str, _config: TStrategyConfig
) -> bool:
    if not _present(
        row, "macd_hist", "prev_macd_hist", "ema_fast", "prev_close"
    ):
        return False
    if side == "SELL":
        return bool(
            row["macd_hist"] < row["prev_macd_hist"]
            and row["close"] >= row["ema_fast"]
            and row["close"] < row["prev_close"]
        )
    return bool(
        row["macd_hist"] > row["prev_macd_hist"]
        and row["close"] <= row["ema_fast"]
        and row["close"] > row["prev_close"]
    )


def _bollinger_reversion_entry(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(
        row,
        "zscore",
        "rsi",
        "vwap",
        "volume_ratio",
        "trend_strength_atr",
        "lower_wick_ratio",
        "upper_wick_ratio",
    ):
        return False
    regime_ok = row["trend_strength_atr"] <= config.max_trend_strength_atr
    volume_ok = row["volume_ratio"] >= config.min_volume_ratio
    if side == "BUY":
        return bool(
            regime_ok
            and volume_ok
            and row["zscore"] <= -config.bollinger_z
            and row["rsi"] <= config.entry_rsi
            and row["close"] < row["vwap"]
            and row["lower_wick_ratio"] >= config.reversal_wick_ratio
        )
    return bool(
        regime_ok
        and volume_ok
        and row["zscore"] >= config.bollinger_z
        and row["rsi"] >= config.exit_rsi
        and row["close"] > row["vwap"]
        and row["upper_wick_ratio"] >= config.reversal_wick_ratio
    )


def _bollinger_reversion_exit(
    row: pd.Series, side: str, _config: TStrategyConfig
) -> bool:
    if not _present(row, "zscore", "rsi", "vwap"):
        return False
    if side == "SELL":
        return bool(
            (row["zscore"] >= 0 or row["close"] >= row["vwap"])
            and row["rsi"] >= 50
        )
    return bool(
        (row["zscore"] <= 0 or row["close"] <= row["vwap"])
        and row["rsi"] <= 50
    )


def _opening_range_entry(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(
        row,
        "opening_range_high",
        "opening_range_low",
        "atr",
        "volume_ratio",
        "vwap",
        "ema_fast",
        "ema_slow",
        "body_ratio",
    ):
        return False
    buffer = config.breakout_atr_buffer * row["atr"]
    if side == "BUY":
        return bool(
            row["close"] >= row["opening_range_high"] + buffer
            and row["volume_ratio"] >= config.min_volume_ratio
            and row["close"] >= row["vwap"]
            and row["ema_fast"] >= row["ema_slow"]
            and row["body_ratio"] >= 0.5
        )
    return bool(
        row["close"] <= row["opening_range_low"] - buffer
        and row["volume_ratio"] >= config.min_volume_ratio
        and row["close"] <= row["vwap"]
        and row["ema_fast"] <= row["ema_slow"]
        and row["body_ratio"] >= 0.5
    )


def _opening_range_exit(
    row: pd.Series, side: str, _config: TStrategyConfig
) -> bool:
    if not _present(
        row,
        "opening_range_high",
        "opening_range_low",
        "macd_hist",
        "prev_macd_hist",
        "prev_close",
    ):
        return False
    if side == "SELL":
        return bool(
            row["close"] > row["opening_range_high"]
            and row["macd_hist"] < row["prev_macd_hist"]
            and row["close"] < row["prev_close"]
        )
    return bool(
        row["close"] < row["opening_range_low"]
        and row["macd_hist"] > row["prev_macd_hist"]
        and row["close"] > row["prev_close"]
    )


def _time_of_day_volume_entry(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(
        row,
        "relative_volume_tod",
        "volume_tod_history_days",
        "macd_hist",
        "prev_macd_hist",
        "ema_fast",
    ):
        return False
    history_ok = (
        row["volume_tod_history_days"]
        >= config.min_time_of_day_history_days
    )
    volume_ok = (
        row["relative_volume_tod"] >= config.relative_volume_tod_threshold
    )
    if side == "BUY":
        return bool(
            history_ok
            and volume_ok
            and row["macd_hist"] > row["prev_macd_hist"]
            and row["close"] >= row["ema_fast"]
        )
    return bool(
        history_ok
        and volume_ok
        and row["macd_hist"] < row["prev_macd_hist"]
        and row["close"] <= row["ema_fast"]
    )


def _time_of_day_volume_exit(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    return _macd_volume_exit(row, side, config)


def _market_residual_entry(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(row, "market_residual_zscore"):
        return False
    if side == "BUY":
        return bool(
            row["market_residual_zscore"] <= -config.residual_z_threshold
        )
    return bool(
        row["market_residual_zscore"] >= config.residual_z_threshold
    )


def _market_residual_exit(
    row: pd.Series, side: str, _config: TStrategyConfig
) -> bool:
    if not _present(row, "market_residual_zscore"):
        return False
    if side == "SELL":
        return bool(row["market_residual_zscore"] >= 0)
    return bool(row["market_residual_zscore"] <= 0)


def _multi_timeframe_entry(
    row: pd.Series, side: str, config: TStrategyConfig
) -> bool:
    if not _present(
        row,
        "daily_trend",
        "higher_timeframe_trend",
        "pullback_distance_atr",
        "macd_hist",
        "prev_macd_hist",
    ):
        return False
    pullback_ok = (
        row["pullback_distance_atr"] <= config.pullback_tolerance_atr
    )
    if side == "BUY":
        return bool(
            row["daily_trend"] > 0
            and row["higher_timeframe_trend"] > 0
            and pullback_ok
            and row["macd_hist"] > row["prev_macd_hist"]
        )
    return bool(
        row["daily_trend"] < 0
        and row["higher_timeframe_trend"] < 0
        and pullback_ok
        and row["macd_hist"] < row["prev_macd_hist"]
    )


def _multi_timeframe_exit(
    row: pd.Series, side: str, _config: TStrategyConfig
) -> bool:
    if not _present(
        row,
        "higher_timeframe_trend",
        "macd_hist",
        "prev_macd_hist",
        "ema_fast",
    ):
        return False
    if side == "SELL":
        return bool(
            (
                row["higher_timeframe_trend"] <= 0
                or row["close"] >= row["ema_fast"]
            )
            and row["macd_hist"] < row["prev_macd_hist"]
        )
    return bool(
        (
            row["higher_timeframe_trend"] >= 0
            or row["close"] <= row["ema_fast"]
        )
        and row["macd_hist"] > row["prev_macd_hist"]
    )


def _candidate(
    row: pd.Series,
    side: str,
    is_entry: bool,
    config: TStrategyConfig,
) -> bool:
    candidates = {
        "causal_mean_reversion_v1": (
            _mean_reversion_entry,
            _mean_reversion_exit,
        ),
        "macd_volume_momentum_v1": (
            _macd_volume_entry,
            _macd_volume_exit,
        ),
        "vwap_bollinger_reversion_v1": (
            _bollinger_reversion_entry,
            _bollinger_reversion_exit,
        ),
        "opening_range_breakout_v1": (
            _opening_range_entry,
            _opening_range_exit,
        ),
        "time_of_day_volume_momentum_v1": (
            _time_of_day_volume_entry,
            _time_of_day_volume_exit,
        ),
        "market_residual_reversal_v1": (
            _market_residual_entry,
            _market_residual_exit,
        ),
        "multi_timeframe_pullback_v1": (
            _multi_timeframe_entry,
            _multi_timeframe_exit,
        ),
    }
    entry_candidate, exit_candidate = candidates[config.strategy]
    return (
        entry_candidate(row, side, config)
        if is_entry
        else exit_candidate(row, side, config)
    )


def _confirmed(row: pd.Series, side: str) -> bool:
    if not _present(row, "prev_close", "prev_rsi"):
        return False
    if side == "BUY":
        return bool(
            row["close"] > row["prev_close"]
            and row["close"] >= row["open"]
            and row["rsi"] >= row["prev_rsi"]
        )
    return bool(
        row["close"] < row["prev_close"]
        and row["close"] <= row["open"]
        and row["rsi"] <= row["prev_rsi"]
    )


def _bounded(value: float) -> float:
    if pd.isna(value):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _confidence(
    row: pd.Series,
    side: str,
    is_entry: bool,
    config: TStrategyConfig,
) -> float:
    if config.strategy == "macd_volume_momentum_v1":
        atr = max(float(row["atr"]), 1e-9) if _present(row, "atr") else 1.0
        momentum = _bounded(abs(float(row["macd_hist"])) / atr)
        volume = _bounded(float(row["volume_ratio"]) / max(config.min_volume_ratio * 2, 0.01))
        alignment = _bounded(abs(float(row["ema_fast"] - row["ema_slow"])) / atr)
        score = 0.4 * momentum + 0.35 * volume + 0.25 * alignment
    elif config.strategy == "time_of_day_volume_momentum_v1":
        relative_volume = _bounded(
            float(row["relative_volume_tod"])
            / max(config.relative_volume_tod_threshold * 2, 0.01)
        )
        atr = max(float(row["atr"]), 1e-9)
        momentum = _bounded(abs(float(row["macd_hist"])) / atr)
        score = 0.6 * relative_volume + 0.4 * momentum
    elif config.strategy == "market_residual_reversal_v1":
        score = _bounded(
            abs(float(row["market_residual_zscore"]))
            / max(config.residual_z_threshold * 2, 0.01)
        )
    elif config.strategy == "multi_timeframe_pullback_v1":
        proximity = 1 - _bounded(
            float(row["pullback_distance_atr"])
            / max(config.pullback_tolerance_atr, 0.01)
        )
        alignment = (
            1.0
            if row["daily_trend"] == row["higher_timeframe_trend"]
            else 0.0
        )
        score = 0.6 * proximity + 0.4 * alignment
    elif config.strategy == "opening_range_breakout_v1":
        atr = max(float(row["atr"]), 1e-9)
        boundary = (
            float(row["opening_range_high"])
            if side == "BUY"
            else float(row["opening_range_low"])
        )
        breakout = _bounded(abs(float(row["close"]) - boundary) / atr)
        volume = _bounded(float(row["volume_ratio"]) / max(config.min_volume_ratio * 2, 0.01))
        body = _bounded(float(row["body_ratio"]))
        score = 0.45 * breakout + 0.35 * volume + 0.2 * body
    else:
        threshold = (
            config.bollinger_z
            if config.strategy == "vwap_bollinger_reversion_v1" and is_entry
            else (config.entry_z if is_entry else config.exit_z)
        )
        z_strength = _bounded(abs(float(row["zscore"])) / max(threshold * 2, 0.01))
        rsi_strength = (
            (100.0 - float(row["rsi"])) / 100.0
            if side == "BUY"
            else float(row["rsi"]) / 100.0
        )
        vwap_strength = _bounded(abs(float(row["vwap_deviation"])) * 100.0)
        score = 0.5 * z_strength + 0.3 * rsi_strength + 0.2 * vwap_strength
        if config.strategy == "vwap_bollinger_reversion_v1":
            wick = row["lower_wick_ratio"] if side == "BUY" else row["upper_wick_ratio"]
            score = 0.8 * score + 0.2 * _bounded(float(wick))
    return round(_bounded(score), 4)


def generate_signals(
    frame: pd.DataFrame, config: TStrategyConfig
) -> list[dict[str, Any]]:
    """Generate alternating decisions from trailing features only."""
    first_side = "BUY" if config.direction == "buy_first" else "SELL"
    second_side = "SELL" if first_side == "BUY" else "BUY"
    expected_side = first_side
    pending_since: int | None = None
    cooldown_until = -1
    completed_round_trips = 0
    signals: list[dict[str, Any]] = []

    for index, row in frame.iterrows():
        if (
            index < cooldown_until
            or completed_round_trips >= config.max_round_trips
        ):
            continue

        is_entry = expected_side == first_side
        candidate = _candidate(row, expected_side, is_entry, config)
        if pending_since is None and candidate:
            pending_since = int(index)

        if pending_since is None:
            continue
        if int(index) - pending_since > config.confirmation_bars:
            pending_since = int(index) if candidate else None
            continue
        if not _confirmed(row, expected_side):
            continue

        phase = "entry" if is_entry else "exit"
        signals.append(
            {
                "signal_id": f"sig-{len(signals) + 1:03d}",
                "bar_index": int(index),
                "decision_time": row["date"].isoformat(),
                "side": expected_side,
                "decision_price": round(float(row["close"]), 4),
                "strategy": config.strategy,
                "confidence": _confidence(
                    row, expected_side, is_entry, config
                ),
                "confidence_kind": "rule_score_v2",
                "reason_codes": [
                    f"{config.strategy}_{phase}_confirmed",
                    "price_direction_confirmed",
                ],
                "features": feature_snapshot(row),
            }
        )
        if expected_side == second_side:
            completed_round_trips += 1
        expected_side = (
            second_side if expected_side == first_side else first_side
        )
        pending_since = None
        cooldown_until = int(index) + 1 + config.cooldown_bars

    return signals

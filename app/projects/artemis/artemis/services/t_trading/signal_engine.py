from __future__ import annotations

from typing import Any

import pandas as pd

from artemis.models.t_trading import TStrategyConfig
from artemis.services.t_trading.features import feature_snapshot


def _entry_candidate(row: pd.Series, side: str, config: TStrategyConfig) -> bool:
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


def _exit_candidate(row: pd.Series, side: str, config: TStrategyConfig) -> bool:
    if side == "SELL":
        return bool(
            (row["zscore"] >= config.exit_z or row["rsi"] >= config.exit_rsi)
            and row["close"] >= row["vwap"]
        )
    return bool(
        (row["zscore"] <= -config.exit_z or row["rsi"] <= config.entry_rsi)
        and row["close"] <= row["vwap"]
    )


def _confirmed(row: pd.Series, side: str) -> bool:
    if pd.isna(row["prev_close"]) or pd.isna(row["prev_rsi"]):
        return False
    if side == "BUY":
        return bool(row["close"] > row["prev_close"] and row["close"] >= row["open"] and row["rsi"] >= row["prev_rsi"])
    return bool(row["close"] < row["prev_close"] and row["close"] <= row["open"] and row["rsi"] <= row["prev_rsi"])


def _confidence(row: pd.Series, side: str, config: TStrategyConfig) -> float:
    z_threshold = config.entry_z if side == ("BUY" if config.direction == "buy_first" else "SELL") else config.exit_z
    z_strength = min(abs(float(row["zscore"])) / max(z_threshold, 0.01), 2.0) / 2.0
    rsi_strength = (100.0 - float(row["rsi"])) / 100.0 if side == "BUY" else float(row["rsi"]) / 100.0
    vwap_strength = min(abs(float(row["vwap_deviation"])) * 100.0, 1.0)
    return round(max(0.0, min(1.0, 0.5 * z_strength + 0.3 * rsi_strength + 0.2 * vwap_strength)), 4)


def generate_signals(frame: pd.DataFrame, config: TStrategyConfig) -> list[dict[str, Any]]:
    """Generate alternating decisions from trailing features only."""
    first_side = "BUY" if config.direction == "buy_first" else "SELL"
    second_side = "SELL" if first_side == "BUY" else "BUY"
    expected_side = first_side
    pending_since: int | None = None
    cooldown_until = -1
    completed_round_trips = 0
    signals: list[dict[str, Any]] = []

    for index, row in frame.iterrows():
        if index >= len(frame) - 1 or index < cooldown_until or completed_round_trips >= config.max_round_trips:
            continue
        if pd.isna(row["zscore"]) or pd.isna(row["rsi"]) or pd.isna(row["vwap"]):
            continue

        is_entry = expected_side == first_side
        candidate = _entry_candidate(row, expected_side, config) if is_entry else _exit_candidate(row, expected_side, config)
        if pending_since is None and candidate:
            pending_since = int(index)

        if pending_since is None:
            continue
        if int(index) - pending_since > config.confirmation_bars:
            pending_since = int(index) if candidate else None
            continue
        if not _confirmed(row, expected_side):
            continue

        reason = "mean_reversion_entry_confirmed" if is_entry else "mean_reversion_exit_confirmed"
        signals.append(
            {
                "signal_id": f"sig-{len(signals) + 1:03d}",
                "bar_index": int(index),
                "decision_time": row["date"].isoformat(),
                "side": expected_side,
                "decision_price": round(float(row["close"]), 4),
                "confidence": _confidence(row, expected_side, config),
                "reason_codes": [reason, "price_reversal", "vwap_side_confirmed"],
                "features": feature_snapshot(row),
            }
        )
        if expected_side == second_side:
            completed_round_trips += 1
        expected_side = second_side if expected_side == first_side else first_side
        pending_since = None
        cooldown_until = int(index) + 1 + config.cooldown_bars

    return signals

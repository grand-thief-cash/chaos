from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from artemis.models.t_trading import TSignalEvaluationConfig


def _round(value: float | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), 6)


def _first_touch(
    future: pd.DataFrame,
    *,
    side: str,
    reference_price: float,
    target_return: float,
    stop_return: float,
) -> tuple[str, int | None]:
    for step, (_, bar) in enumerate(future.iterrows(), start=1):
        if side == "BUY":
            target_hit = float(bar["high"]) / reference_price - 1 >= target_return
            stop_hit = 1 - float(bar["low"]) / reference_price >= stop_return
        else:
            target_hit = 1 - float(bar["low"]) / reference_price >= target_return
            stop_hit = float(bar["high"]) / reference_price - 1 >= stop_return
        if target_hit and stop_hit:
            return "ambiguous_same_bar", step
        if target_hit:
            return "target_first", step
        if stop_hit:
            return "stop_first", step
    return "no_touch", None


def _outcome(
    frame: pd.DataFrame,
    signal: dict[str, Any],
    horizon: int,
    config: TSignalEvaluationConfig,
) -> dict[str, Any]:
    index = int(signal["bar_index"])
    base = {
        "signal_id": signal["signal_id"],
        "strategy": signal.get("strategy"),
        "side": signal["side"],
        "decision_time": signal["decision_time"],
        "decision_price": signal["decision_price"],
        "horizon_bars": horizon,
    }
    if index + horizon >= len(frame):
        return {
            **base,
            "evaluable": False,
            "reason": "insufficient_future_bars",
        }

    future = frame.iloc[index + 1 : index + horizon + 1]
    reference_price = float(signal["decision_price"])
    side = signal["side"]
    direction = 1.0 if side == "BUY" else -1.0
    close_return = direction * (
        float(future.iloc[-1]["close"]) / reference_price - 1
    )
    if side == "BUY":
        favorable_path = (
            future["high"].astype(float) / reference_price - 1
        ).clip(lower=0)
        adverse_path = (
            1 - future["low"].astype(float) / reference_price
        ).clip(lower=0)
    else:
        favorable_path = (
            1 - future["low"].astype(float) / reference_price
        ).clip(lower=0)
        adverse_path = (
            future["high"].astype(float) / reference_price - 1
        ).clip(lower=0)

    first_touch, first_touch_bar = _first_touch(
        future,
        side=side,
        reference_price=reference_price,
        target_return=config.target_return,
        stop_return=config.stop_return,
    )
    return {
        **base,
        "evaluable": True,
        "directional_return": _round(close_return),
        "direction_correct": bool(close_return > 0),
        "mfe": _round(float(favorable_path.max())),
        "mae": _round(float(adverse_path.max())),
        "time_to_mfe_bars": int(np.argmax(favorable_path.to_numpy())) + 1,
        "time_to_mae_bars": int(np.argmax(adverse_path.to_numpy())) + 1,
        "target_touched": bool(favorable_path.max() >= config.target_return),
        "stop_touched": bool(adverse_path.max() >= config.stop_return),
        "first_touch": first_touch,
        "first_touch_bar": first_touch_bar,
    }


def aggregate_outcomes(
    outcomes: list[dict[str, Any]],
    *,
    horizon: int,
    side: str | None = None,
    strategy: str | None = None,
) -> dict[str, Any]:
    selected = [
        outcome
        for outcome in outcomes
        if outcome["horizon_bars"] == horizon
        and (side is None or outcome["side"] == side)
        and (strategy is None or outcome["strategy"] == strategy)
    ]
    evaluable = [outcome for outcome in selected if outcome["evaluable"]]
    result: dict[str, Any] = {
        "horizon_bars": horizon,
        "side": side or "ALL",
        "strategy": strategy,
        "signal_count": len(selected),
        "evaluable_signal_count": len(evaluable),
        "insufficient_future_count": len(selected) - len(evaluable),
        "directional_accuracy": None,
        "mean_directional_return": None,
        "median_directional_return": None,
        "mean_mfe": None,
        "median_mfe": None,
        "mean_mae": None,
        "median_mae": None,
        "edge_ratio": None,
        "target_touch_rate": None,
        "stop_touch_rate": None,
        "target_first_rate": None,
        "stop_first_rate": None,
        "ambiguous_same_bar_rate": None,
    }
    if not evaluable:
        return result

    directional_returns = np.array(
        [outcome["directional_return"] for outcome in evaluable], dtype=float
    )
    mfes = np.array([outcome["mfe"] for outcome in evaluable], dtype=float)
    maes = np.array([outcome["mae"] for outcome in evaluable], dtype=float)
    mean_mae = float(maes.mean())
    count = len(evaluable)
    result.update(
        {
            "directional_accuracy": _round(
                sum(outcome["direction_correct"] for outcome in evaluable)
                / count
            ),
            "mean_directional_return": _round(
                float(directional_returns.mean())
            ),
            "median_directional_return": _round(
                float(np.median(directional_returns))
            ),
            "mean_mfe": _round(float(mfes.mean())),
            "median_mfe": _round(float(np.median(mfes))),
            "mean_mae": _round(mean_mae),
            "median_mae": _round(float(np.median(maes))),
            "edge_ratio": _round(
                float(mfes.mean()) / mean_mae if mean_mae > 0 else None
            ),
            "target_touch_rate": _round(
                sum(outcome["target_touched"] for outcome in evaluable) / count
            ),
            "stop_touch_rate": _round(
                sum(outcome["stop_touched"] for outcome in evaluable) / count
            ),
            "target_first_rate": _round(
                sum(
                    outcome["first_touch"] == "target_first"
                    for outcome in evaluable
                )
                / count
            ),
            "stop_first_rate": _round(
                sum(
                    outcome["first_touch"] == "stop_first"
                    for outcome in evaluable
                )
                / count
            ),
            "ambiguous_same_bar_rate": _round(
                sum(
                    outcome["first_touch"] == "ambiguous_same_bar"
                    for outcome in evaluable
                )
                / count
            ),
        }
    )
    return result


def evaluate_signals(
    frame: pd.DataFrame,
    signals: list[dict[str, Any]],
    config: TSignalEvaluationConfig,
    *,
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate post-signal paths. This module is never imported by signal generation."""
    outcomes = [
        _outcome(frame, signal, horizon, config)
        for signal in signals
        for horizon in config.horizons_bars
    ]
    by_horizon = [
        {
            **aggregate_outcomes(outcomes, horizon=horizon),
            "by_side": {
                side: aggregate_outcomes(
                    outcomes, horizon=horizon, side=side
                )
                for side in ("BUY", "SELL")
            },
        }
        for horizon in config.horizons_bars
    ]
    selected_strategies = strategies or sorted(
        {
            str(outcome["strategy"])
            for outcome in outcomes
            if outcome.get("strategy")
        }
    )
    by_strategy = [
        aggregate_outcomes(
            outcomes,
            horizon=config.primary_horizon_bars,
            strategy=strategy,
        )
        for strategy in selected_strategies
    ]
    by_strategy_side = [
        aggregate_outcomes(
            outcomes,
            horizon=config.primary_horizon_bars,
            strategy=strategy,
            side=side,
        )
        for strategy in selected_strategies
        for side in ("BUY", "SELL")
    ]
    return {
        "evaluation_kind": "forward_event_study_v1",
        "price_basis": "decision_bar_close",
        "future_window": "bars_after_decision",
        "same_bar_touch_policy": "ambiguous",
        "config": config.model_dump(mode="json"),
        "summary": aggregate_outcomes(
            outcomes, horizon=config.primary_horizon_bars
        ),
        "by_horizon": by_horizon,
        "by_strategy": by_strategy,
        "by_strategy_side": by_strategy_side,
        "outcomes": outcomes,
    }


def summarize_signal_evaluations(
    replays: list[dict[str, Any]],
    *,
    primary_horizon: int,
) -> dict[str, Any]:
    outcomes = [
        outcome
        for replay in replays
        for outcome in replay["signal_evaluation"]["outcomes"]
    ]
    summary = aggregate_outcomes(outcomes, horizon=primary_horizon)
    summary.update(
        {
            "replay_days": len(replays),
            "days_with_signals": sum(
                bool(replay["signals"]) for replay in replays
            ),
        }
    )
    return summary


def summarize_signal_evaluations_by_strategy(
    replays: list[dict[str, Any]],
    *,
    primary_horizon: int,
    strategies: list[str] | None = None,
) -> list[dict[str, Any]]:
    outcomes = [
        outcome
        for replay in replays
        for outcome in replay["signal_evaluation"]["outcomes"]
    ]
    selected_strategies = strategies or sorted(
        {
            str(outcome["strategy"])
            for outcome in outcomes
            if outcome.get("strategy")
        }
    )
    return [
        aggregate_outcomes(
            outcomes,
            horizon=primary_horizon,
            strategy=strategy,
        )
        for strategy in selected_strategies
    ]

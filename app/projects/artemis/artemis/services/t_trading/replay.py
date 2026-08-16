from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import math
from typing import Any
from uuid import uuid4

import pandas as pd

from artemis.models.t_trading import TBatchReplayRequest, TReplayRequest
from artemis.services.t_trading.execution import pair_round_trips, simulate_fills
from artemis.services.t_trading.features import (
    attach_strategy_context,
    build_causal_features,
)
from artemis.services.t_trading.report import summarize_round_trips
from artemis.services.t_trading.signal_evaluation import (
    evaluate_signals,
    summarize_signal_evaluations,
    summarize_signal_evaluations_by_strategy,
)
from artemis.services.t_trading.signal_engine import generate_signals


SHANGHAI = timezone(timedelta(hours=8))


class NoMinuteDataError(ValueError):
    pass


def _intraday_session_bounds(trade_date: date) -> tuple[str, str]:
    """A-share observation window including auction through the close."""
    start = datetime.combine(trade_date, time(9, 15), tzinfo=SHANGHAI)
    end = datetime.combine(
        trade_date,
        time(15, 0, 59, 999999),
        tzinfo=SHANGHAI,
    )
    return start.isoformat(), end.isoformat()


def _public_bars(frame) -> list[dict[str, Any]]:
    fields = ("date", "open", "high", "low", "close", "volume", "amount")
    result = []
    for _, row in frame.iterrows():
        item = {"date": row["date"].isoformat()}
        for field in fields[1:]:
            item[field] = round(float(row[field]), 4)
        result.append(item)
    return result


def _indicator_set(frame, strategy) -> dict[str, Any]:
    """Expose causal chart points calculated with this strategy's parameters."""
    fields = (
        "ema_fast",
        "ema_slow",
        "macd",
        "macd_signal",
        "macd_hist",
        "vwap",
        "rsi",
        "volume_ratio",
        "relative_volume_tod",
        "opening_range_high",
        "opening_range_low",
        "ema_deviation_atr",
        "macd_hist_delta",
        "macd_hist_rising_bars",
        "macd_hist_falling_bars",
        "recent_volume_ratio_max",
    )
    points = []
    for _, row in frame.iterrows():
        point: dict[str, Any] = {"date": row["date"].isoformat()}
        for field in fields:
            raw = row.get(field)
            value = float(raw) if raw is not None else math.nan
            point[field] = round(value, 6) if math.isfinite(value) else None
        mean = float(row.get("rolling_mean", math.nan))
        std = float(row.get("rolling_std", math.nan))
        if math.isfinite(mean) and math.isfinite(std):
            point["bollinger_upper"] = round(
                mean + strategy.bollinger_z * std, 6
            )
            point["bollinger_lower"] = round(
                mean - strategy.bollinger_z * std, 6
            )
        else:
            point["bollinger_upper"] = None
            point["bollinger_lower"] = None
        points.append(point)
    return {
        "strategy": strategy.strategy,
        "parameters": strategy.model_dump(mode="json"),
        "points": points,
    }


def _quality(frame, period: str) -> dict[str, Any]:
    expected_minutes = {"min1": 1, "min5": 5}[period]
    deltas = frame["date"].diff().dt.total_seconds().div(60)
    session_break = deltas >= 60
    gaps = deltas[(deltas > expected_minutes * 1.5) & ~session_break]
    return {
        "bar_count": int(len(frame)),
        "zero_volume_bars": int((frame["volume"] <= 0).sum()),
        "unexpected_gap_count": int(len(gaps)),
        "first_bar_time": frame.iloc[0]["date"].isoformat(),
        "last_bar_time": frame.iloc[-1]["date"].isoformat(),
    }


def run_replay_from_bars(
    request: TReplayRequest,
    bars: list[dict[str, Any]],
    *,
    symbol: str = "",
    context_bars: dict[str, list[dict[str, Any]]] | None = None,
    context_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure in-memory replay entry point used by the API and tests."""
    if request.persistence_mode != "ephemeral":
        raise ValueError("only persistence_mode=ephemeral is supported")
    if not bars:
        raise NoMinuteDataError(f"no {request.period} bars for {request.trade_date.isoformat()}")

    context_bars = context_bars or {}
    target_times = set(
        pd.to_datetime(
            [item.get("date") for item in bars],
            errors="coerce",
            utc=True,
        ).dropna()
    )
    feature_bars = [*context_bars.get("warmup_bars", []), *bars]
    strategy_frames = []
    signals: list[dict[str, Any]] = []
    for strategy_index, strategy in enumerate(request.effective_strategies, start=1):
        full_strategy_frame = build_causal_features(
            feature_bars,
            strategy.window,
            ema_fast=strategy.ema_fast,
            ema_slow=strategy.ema_slow,
            macd_signal=strategy.macd_signal,
            atr_window=strategy.atr_window,
            opening_range_bars=strategy.opening_range_bars,
            volume_confirmation_window=(
                strategy.volume_confirmation_window
            ),
        )
        full_strategy_frame = attach_strategy_context(
            full_strategy_frame,
            historical_bars=context_bars.get("historical_bars"),
            benchmark_bars=context_bars.get("benchmark_bars"),
            daily_bars=context_bars.get("daily_bars"),
            higher_timeframe_bars=context_bars.get("higher_timeframe_bars"),
            market_beta_window=strategy.market_beta_window,
            higher_ema_fast=strategy.higher_ema_fast,
            higher_ema_slow=strategy.higher_ema_slow,
            daily_trend_window=strategy.daily_trend_window,
        )
        strategy_frame = full_strategy_frame[
            full_strategy_frame["date"].isin(target_times)
        ].copy().reset_index(drop=True)
        if strategy_frame.empty:
            raise NoMinuteDataError(
                f"no {request.period} target bars for "
                f"{request.trade_date.isoformat()} after warmup"
            )
        local_signals = generate_signals(strategy_frame, strategy)
        for local_index, signal in enumerate(local_signals, start=1):
            signal["signal_id"] = (
                f"sig-{strategy_index:02d}-{local_index:03d}"
            )
        signals.extend(local_signals)
        strategy_frames.append(strategy_frame)

    signals.sort(
        key=lambda item: (
            int(item["bar_index"]),
            str(item["strategy"]),
            str(item["side"]),
        )
    )
    frame = strategy_frames[0]
    signal_evaluation = evaluate_signals(
        frame,
        signals,
        request.evaluation,
        strategies=[
            item.strategy for item in request.effective_strategies
        ],
    )
    if request.include_execution_simulation:
        fills = simulate_fills(frame, signals, request.execution)
        round_trips = pair_round_trips(
            frame, fills, request.effective_strategies[0]
        )
    else:
        fills = []
        round_trips = []
    return {
        "run_meta": {
            "run_id": f"t-wb-{uuid4().hex}",
            "engine_version": "+".join(
                item.strategy for item in request.effective_strategies
            ),
            "strategies": [
                item.strategy for item in request.effective_strategies
            ],
            "security_id": request.security_id,
            "symbol": symbol,
            "trade_date": request.trade_date.isoformat(),
            "period": request.period,
            "adjust": request.adjust,
            "persistence_mode": "ephemeral",
            "causality": "signal_at_bar_close_evaluate_subsequent_bars",
            "execution_simulation": (
                "next_bar_open"
                if request.include_execution_simulation
                else "disabled"
            ),
        },
        "bars": _public_bars(frame),
        "indicator_sets": [
            _indicator_set(strategy_frame, strategy)
            for strategy_frame, strategy in zip(
                strategy_frames, request.effective_strategies
            )
        ],
        "signals": signals,
        "signal_evaluation": signal_evaluation,
        "fills": fills,
        "round_trips": round_trips,
        "summary": signal_evaluation["summary"],
        "execution_summary": {
            "enabled": request.include_execution_simulation,
            **summarize_round_trips(round_trips),
        },
        "data_quality": {
            **_quality(frame, request.period),
            "strategy_context": context_diagnostics or {
                key: {"bar_count": len(value)}
                for key, value in context_bars.items()
            },
        },
    }


def run_replay(request: TReplayRequest) -> dict[str, Any]:
    from artemis.services.workbench import get_market_bars

    start, end = _intraday_session_bounds(request.trade_date)
    market_data = get_market_bars(
        security_id=request.security_id,
        start_date=start,
        end_date=end,
        period=request.period,
        adjust=request.adjust,
        asset_type="stock",
        market="zh_a",
        source=request.source,
        use_cache=False,
    )
    market_bars = market_data.get("bars", [])
    if not market_bars:
        raise NoMinuteDataError(
            f"no {request.period} bars for {request.trade_date.isoformat()}"
        )
    strategy_names = {
        item.strategy for item in request.effective_strategies
    }
    context_bars: dict[str, list[dict[str, Any]]] = {}
    context_diagnostics: dict[str, Any] = {}

    def load_context(name: str, **kwargs: Any) -> None:
        try:
            data = get_market_bars(
                source=request.source,
                use_cache=False,
                **kwargs,
            )
            rows = data.get("bars", [])
            context_bars[name] = rows
            context_diagnostics[name] = {"bar_count": len(rows)}
        except Exception as exc:
            context_bars[name] = []
            context_diagnostics[name] = {
                "bar_count": 0,
                "error_type": type(exc).__name__,
                "reason": str(exc),
            }

    # EMA/MACD/RSI/ATR are continuous indicators. Brokerage terminals draw
    # them from the opening bar because they seed the calculation with prior
    # bars; loading 45 calendar days safely covers long holidays and the
    # largest configurable minute window. Session VWAP/opening range still
    # reset by Shanghai trade date inside build_causal_features().
    warmup_start = request.trade_date - timedelta(days=45)
    warmup_end = request.trade_date - timedelta(days=1)
    load_context(
        "warmup_bars",
        security_id=request.security_id,
        start_date=_intraday_session_bounds(warmup_start)[0],
        end_date=_intraday_session_bounds(warmup_end)[1],
        period=request.period,
        adjust=request.adjust,
        asset_type="stock",
        market="zh_a",
    )

    if "time_of_day_volume_momentum_v1" in strategy_names:
        history_start = request.trade_date - timedelta(days=70)
        history_end = request.trade_date - timedelta(days=1)
        load_context(
            "historical_bars",
            security_id=request.security_id,
            start_date=_intraday_session_bounds(history_start)[0],
            end_date=_intraday_session_bounds(history_end)[1],
            period=request.period,
            adjust=request.adjust,
            asset_type="stock",
            market="zh_a",
        )
    if "market_residual_reversal_v1" in strategy_names:
        benchmark_start = request.trade_date - timedelta(days=7)
        load_context(
            "benchmark_bars",
            security_id=int(request.benchmark_security_id),
            start_date=_intraday_session_bounds(benchmark_start)[0],
            end_date=end,
            period=request.period,
            adjust="nf",
            asset_type="index",
            market="zh_a",
        )
    if "multi_timeframe_pullback_v1" in strategy_names:
        daily_start = request.trade_date - timedelta(days=250)
        daily_end = request.trade_date - timedelta(days=1)
        load_context(
            "daily_bars",
            security_id=request.security_id,
            start_date=daily_start.isoformat(),
            end_date=daily_end.isoformat(),
            period="daily",
            adjust="nf",
            asset_type="stock",
            market="zh_a",
        )
        higher_start = request.trade_date - timedelta(days=45)
        load_context(
            "higher_timeframe_bars",
            security_id=request.security_id,
            start_date=_intraday_session_bounds(higher_start)[0],
            end_date=end,
            period="min30",
            adjust="nf",
            asset_type="stock",
            market="zh_a",
        )

    return run_replay_from_bars(
        request,
        market_bars,
        symbol=market_data.get("symbol", ""),
        context_bars=context_bars,
        context_diagnostics=context_diagnostics,
    )


def _dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def run_batch_replay(request: TBatchReplayRequest) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for security_id in request.security_ids:
        for trade_date in _dates(request.start_date, request.end_date):
            replay_request = TReplayRequest(
                security_id=security_id,
                trade_date=trade_date,
                period=request.period,
                adjust=request.adjust,
                source=request.source,
                persistence_mode=request.persistence_mode,
                strategy=request.strategy,
                strategies=request.strategies,
                benchmark_security_id=request.benchmark_security_id,
                evaluation=request.evaluation,
                include_execution_simulation=request.include_execution_simulation,
                execution=request.execution,
            )
            try:
                result = run_replay(replay_request)
                results.append(result)
            except NoMinuteDataError as exc:
                skipped.append({"security_id": security_id, "trade_date": trade_date.isoformat(), "reason": str(exc)})
            except Exception as exc:
                failures.append({
                    "security_id": security_id,
                    "trade_date": trade_date.isoformat(),
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                })

    by_security = []
    for security_id in request.security_ids:
        subset = [result for result in results if result["run_meta"]["security_id"] == security_id]
        by_security.append({
            "security_id": security_id,
            **summarize_signal_evaluations(
                subset,
                primary_horizon=request.evaluation.primary_horizon_bars,
            ),
        })
    by_day = []
    for trade_date in _dates(request.start_date, request.end_date):
        day_text = trade_date.isoformat()
        subset = [result for result in results if result["run_meta"]["trade_date"] == day_text]
        by_day.append({
            "trade_date": day_text,
            **summarize_signal_evaluations(
                subset,
                primary_horizon=request.evaluation.primary_horizon_bars,
            ),
        })

    if request.include_details:
        returned_results = results
    else:
        returned_results = [
            {
                "run_meta": result["run_meta"],
                "summary": result["summary"],
                "data_quality": result["data_quality"],
            }
            for result in results
        ]
    return {
        "run_meta": {
            "run_id": f"t-batch-{uuid4().hex}",
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "period": request.period,
            "strategies": [
                item.strategy for item in request.effective_strategies
            ],
            "persistence_mode": "ephemeral",
        },
        "summary": summarize_signal_evaluations(
            results,
            primary_horizon=request.evaluation.primary_horizon_bars,
        ),
        "by_security": by_security,
        "by_day": by_day,
        "by_strategy": summarize_signal_evaluations_by_strategy(
            results,
            primary_horizon=request.evaluation.primary_horizon_bars,
            strategies=[
                item.strategy for item in request.effective_strategies
            ],
        ),
        "results": returned_results,
        "skipped": skipped,
        "failures": failures,
    }

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4

from artemis.models.t_trading import TBatchReplayRequest, TReplayRequest
from artemis.services.t_trading.execution import pair_round_trips, simulate_fills
from artemis.services.t_trading.features import build_causal_features
from artemis.services.t_trading.report import summarize_replays, summarize_round_trips
from artemis.services.t_trading.signal_engine import generate_signals


SHANGHAI = timezone(timedelta(hours=8))


class NoMinuteDataError(ValueError):
    pass


def _day_bounds(trade_date: date) -> tuple[str, str]:
    start = datetime.combine(trade_date, time.min, tzinfo=SHANGHAI)
    end = datetime.combine(trade_date, time.max, tzinfo=SHANGHAI)
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


def _quality(frame, period: str) -> dict[str, Any]:
    expected_minutes = {"min5": 5}[period]
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
) -> dict[str, Any]:
    """Pure in-memory replay entry point used by the API and tests."""
    if request.persistence_mode != "ephemeral":
        raise ValueError("only persistence_mode=ephemeral is supported")
    if not bars:
        raise NoMinuteDataError(f"no {request.period} bars for {request.trade_date.isoformat()}")

    frame = build_causal_features(bars, request.strategy.window)
    signals = generate_signals(frame, request.strategy)
    fills = simulate_fills(frame, signals, request.execution)
    round_trips = pair_round_trips(frame, fills, request.strategy)
    return {
        "run_meta": {
            "run_id": f"t-wb-{uuid4().hex}",
            "security_id": request.security_id,
            "symbol": symbol,
            "trade_date": request.trade_date.isoformat(),
            "period": request.period,
            "adjust": request.adjust,
            "persistence_mode": "ephemeral",
            "causality": "decision_at_bar_close_fill_at_next_bar_open",
        },
        "bars": _public_bars(frame),
        "signals": signals,
        "fills": fills,
        "round_trips": round_trips,
        "summary": summarize_round_trips(round_trips),
        "data_quality": _quality(frame, request.period),
    }


def run_replay(request: TReplayRequest) -> dict[str, Any]:
    from artemis.services.workbench import get_market_bars

    start, end = _day_bounds(request.trade_date)
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
    return run_replay_from_bars(request, market_data.get("bars", []), symbol=market_data.get("symbol", ""))


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
        by_security.append({"security_id": security_id, **summarize_replays(subset)})
    by_day = []
    for trade_date in _dates(request.start_date, request.end_date):
        day_text = trade_date.isoformat()
        subset = [result for result in results if result["run_meta"]["trade_date"] == day_text]
        by_day.append({"trade_date": day_text, **summarize_replays(subset)})

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
            "persistence_mode": "ephemeral",
        },
        "summary": summarize_replays(results),
        "by_security": by_security,
        "by_day": by_day,
        "results": returned_results,
        "skipped": skipped,
        "failures": failures,
    }

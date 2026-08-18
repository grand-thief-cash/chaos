from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


def _attach_intraday_reversal_features(
    frame: pd.DataFrame,
    *,
    panic_window_bars: int,
    panic_return_threshold: float,
    panic_volume_ratio: float,
    macd_divergence_lookback: int,
    rebound_confirmation_bars: int,
    rebound_recovery_ratio: float,
    regime_slope_bars: int,
) -> None:
    """Attach causal, session-local reversal evidence in place.

    Evidence is intentionally kept separate from the signal rule so every
    gate can be inspected in replay output.  All rolling windows end at the
    current bar and all reference extrema come from earlier bars only.
    """
    grouped = frame.groupby("_trade_day", sort=False)
    frame["ema_slow_slope_window"] = grouped["ema_slow"].diff(
        regime_slope_bars
    )
    frame["vwap_slope_window"] = grouped["vwap"].diff(regime_slope_bars)
    frame["bearish_regime"] = (
        (frame["close"] < frame["vwap"])
        & (frame["ema_slow_slope_window"] < 0)
        & (frame["vwap_slope_window"] < 0)
    ).astype(float)
    frame["bullish_regime"] = (
        (frame["close"] > frame["vwap"])
        & (frame["ema_slow_slope_window"] > 0)
        & (frame["vwap_slope_window"] > 0)
    ).astype(float)

    raw_fields = (
        "panic_window_return",
        "panic_volume_ratio",
        "bullish_macd_divergence",
        "bearish_macd_divergence",
        "bullish_rebound_recovery",
        "bearish_rebound_recovery",
        "bullish_rebound_structure",
        "bearish_rebound_structure",
    )
    for field in raw_fields:
        frame[field] = np.nan
    frame["bullish_bar_streak"] = 0.0
    frame["bearish_bar_streak"] = 0.0

    for positions in grouped.indices.values():
        positions = np.asarray(positions, dtype=int)
        session = frame.iloc[positions]
        closes = session["close"].to_numpy(dtype=float)
        opens = session["open"].to_numpy(dtype=float)
        lows = session["low"].to_numpy(dtype=float)
        highs = session["high"].to_numpy(dtype=float)
        volumes = session["volume"].to_numpy(dtype=float)
        macd_hist = session["macd_hist"].to_numpy(dtype=float)
        macd = session["macd"].to_numpy(dtype=float)
        size = len(session)

        returns = np.full(size, np.nan)
        volume_ratios = np.full(size, np.nan)
        bullish_divergence = np.zeros(size, dtype=float)
        bearish_divergence = np.zeros(size, dtype=float)
        bullish_recovery = np.full(size, np.nan)
        bearish_recovery = np.full(size, np.nan)
        bullish_structure = np.zeros(size, dtype=float)
        bearish_structure = np.zeros(size, dtype=float)
        bullish_streak = np.zeros(size, dtype=float)
        bearish_streak = np.zeros(size, dtype=float)

        for offset in range(size):
            if offset >= panic_window_bars:
                anchor = closes[offset - panic_window_bars]
                if anchor > 0:
                    returns[offset] = closes[offset] / anchor - 1.0
                prior_volume = volumes[offset - panic_window_bars:offset]
                prior_mean = float(np.mean(prior_volume))
                if prior_mean > 0:
                    volume_ratios[offset] = volumes[offset] / prior_mean

            if closes[offset] > opens[offset]:
                bullish_streak[offset] = (
                    bullish_streak[offset - 1] + 1 if offset else 1
                )
            elif closes[offset] < opens[offset]:
                bearish_streak[offset] = (
                    bearish_streak[offset - 1] + 1 if offset else 1
                )

            divergence_start = max(0, offset - macd_divergence_lookback)
            if offset - divergence_start >= 2:
                prior_lows = lows[divergence_start:offset]
                prior_highs = highs[divergence_start:offset]
                low_offset = divergence_start + int(np.argmin(prior_lows))
                high_offset = divergence_start + int(np.argmax(prior_highs))
                bullish_momentum_diverged = (
                    (
                        np.isfinite(macd_hist[offset])
                        and np.isfinite(macd_hist[low_offset])
                        and macd_hist[offset] > macd_hist[low_offset]
                    )
                    or (
                        np.isfinite(macd[offset])
                        and np.isfinite(macd[low_offset])
                        and macd[offset] > macd[low_offset]
                    )
                )
                bearish_momentum_diverged = (
                    (
                        np.isfinite(macd_hist[offset])
                        and np.isfinite(macd_hist[high_offset])
                        and macd_hist[offset] < macd_hist[high_offset]
                    )
                    or (
                        np.isfinite(macd[offset])
                        and np.isfinite(macd[high_offset])
                        and macd[offset] < macd[high_offset]
                    )
                )
                bullish_divergence[offset] = float(
                    lows[offset] <= lows[low_offset]
                    and bullish_momentum_diverged
                )
                bearish_divergence[offset] = float(
                    highs[offset] >= highs[high_offset]
                    and bearish_momentum_diverged
                )

            structure_start = max(0, offset - panic_window_bars)
            if offset > structure_start:
                prior_opens = opens[structure_start:offset]
                prior_closes = closes[structure_start:offset]
                bearish_bodies = prior_opens - prior_closes
                if np.any(bearish_bodies > 0):
                    local = int(np.argmax(bearish_bodies))
                    body = bearish_bodies[local]
                    bearish_close = prior_closes[local]
                    bullish_recovery[offset] = (
                        closes[offset] - bearish_close
                    ) / body
                    bullish_structure[offset] = float(
                        bullish_streak[offset] >= rebound_confirmation_bars
                        and bullish_recovery[offset]
                        >= rebound_recovery_ratio
                    )
                bullish_bodies = prior_closes - prior_opens
                if np.any(bullish_bodies > 0):
                    local = int(np.argmax(bullish_bodies))
                    body = bullish_bodies[local]
                    bullish_close = prior_closes[local]
                    bearish_recovery[offset] = (
                        bullish_close - closes[offset]
                    ) / body
                    bearish_structure[offset] = float(
                        bearish_streak[offset] >= rebound_confirmation_bars
                        and bearish_recovery[offset]
                        >= rebound_recovery_ratio
                    )

        assignments = {
            "panic_window_return": returns,
            "panic_volume_ratio": volume_ratios,
            "bullish_macd_divergence": bullish_divergence,
            "bearish_macd_divergence": bearish_divergence,
            "bullish_rebound_recovery": bullish_recovery,
            "bearish_rebound_recovery": bearish_recovery,
            "bullish_rebound_structure": bullish_structure,
            "bearish_rebound_structure": bearish_structure,
            "bullish_bar_streak": bullish_streak,
            "bearish_bar_streak": bearish_streak,
        }
        for field, values in assignments.items():
            frame.loc[positions, field] = values

    evidence_window = max(panic_window_bars, rebound_confirmation_bars + 1)

    def recent_max(values: pd.Series) -> pd.Series:
        return values.rolling(evidence_window, min_periods=1).max()

    def recent_min(values: pd.Series) -> pd.Series:
        return values.rolling(evidence_window, min_periods=1).min()

    frame["recent_bearish_shock"] = grouped[
        "panic_window_return"
    ].transform(recent_min)
    frame["recent_bullish_shock"] = grouped[
        "panic_window_return"
    ].transform(recent_max)
    frame["recent_panic_volume_ratio_max"] = grouped[
        "panic_volume_ratio"
    ].transform(recent_max)
    frame["bullish_divergence_recent"] = grouped[
        "bullish_macd_divergence"
    ].transform(recent_max)
    frame["bearish_divergence_recent"] = grouped[
        "bearish_macd_divergence"
    ].transform(recent_max)
    frame["recent_min_ema_deviation_atr"] = grouped[
        "ema_deviation_atr"
    ].transform(recent_min)
    frame["recent_max_ema_deviation_atr"] = grouped[
        "ema_deviation_atr"
    ].transform(recent_max)

    bearish_shock = frame["recent_bearish_shock"] <= -panic_return_threshold
    bullish_shock = frame["recent_bullish_shock"] >= panic_return_threshold
    panic_volume = (
        frame["recent_panic_volume_ratio_max"] >= panic_volume_ratio
    )
    frame["bullish_reversal_evidence_score"] = (
        bearish_shock.astype(int)
        + panic_volume.astype(int)
        + frame["bullish_divergence_recent"].fillna(0).gt(0).astype(int)
        + frame["bullish_rebound_structure"].fillna(0).gt(0).astype(int)
    ).astype(float)
    frame["bearish_reversal_evidence_score"] = (
        bullish_shock.astype(int)
        + panic_volume.astype(int)
        + frame["bearish_divergence_recent"].fillna(0).gt(0).astype(int)
        + frame["bearish_rebound_structure"].fillna(0).gt(0).astype(int)
    ).astype(float)


def build_causal_features(
    bars: list[dict[str, Any]],
    window: int,
    *,
    ema_fast: int = 5,
    ema_slow: int = 13,
    macd_signal: int = 4,
    atr_window: int = 14,
    opening_range_bars: int = 6,
    volume_confirmation_window: int = 3,
    panic_window_bars: int = 5,
    panic_return_threshold: float = 0.02,
    panic_volume_ratio: float = 3.0,
    macd_divergence_lookback: int = 20,
    rebound_confirmation_bars: int = 3,
    rebound_recovery_ratio: float = 0.5,
    regime_slope_bars: int = 5,
    medium_trend_fast_bars: int = 15,
    medium_trend_slow_bars: int = 30,
) -> pd.DataFrame:
    """Build trailing-only features. No negative shift or centered window is used."""
    if not bars:
        raise ValueError("minute bars are empty")

    frame = pd.DataFrame(bars).copy()
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"minute bars missing columns: {sorted(missing)}")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    for column in ("open", "high", "low", "close", "volume", "amount"):
        if column not in frame:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    if frame.empty:
        raise ValueError("minute bars contain no valid rows")
    if ((frame[["open", "high", "low", "close"]] <= 0).any(axis=1)).any():
        raise ValueError("minute bars contain non-positive OHLC values")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("minute bars contain invalid high values")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("minute bars contain invalid low values")

    frame["_trade_day"] = frame["date"].dt.tz_convert(
        "Asia/Shanghai"
    ).dt.date

    frame["return_1"] = frame["close"].pct_change()
    rolling_close = frame["close"].rolling(window, min_periods=window)
    frame["rolling_mean"] = rolling_close.mean()
    frame["rolling_std"] = rolling_close.std(ddof=0).replace(0, np.nan)
    frame["zscore"] = (frame["close"] - frame["rolling_mean"]) / frame["rolling_std"]

    delta = frame["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = gain / loss.replace(0, np.nan)
    frame["rsi"] = 100 - (100 / (1 + rs))
    frame.loc[(loss == 0) & (gain > 0), "rsi"] = 100.0
    frame.loc[(loss == 0) & (gain == 0), "rsi"] = 50.0

    amount = frame["amount"].where(frame["amount"] > 0, frame["close"] * frame["volume"])
    positive_volume = frame["volume"].clip(lower=0)
    cumulative_volume = positive_volume.groupby(frame["_trade_day"]).cumsum()
    cumulative_amount = amount.clip(lower=0).groupby(
        frame["_trade_day"]
    ).cumsum()
    frame["vwap"] = (
        cumulative_amount / cumulative_volume.replace(0, np.nan)
    ).fillna(frame["close"])
    frame["vwap_deviation"] = frame["close"] / frame["vwap"] - 1

    rolling_high = frame["high"].rolling(window, min_periods=window).max()
    rolling_low = frame["low"].rolling(window, min_periods=window).min()
    frame["range_position"] = (frame["close"] - rolling_low) / (rolling_high - rolling_low).replace(0, np.nan)
    frame["volume_median"] = frame["volume"].rolling(window, min_periods=window).median()
    frame["volume_ratio"] = frame["volume"] / frame["volume_median"].replace(0, np.nan)
    frame["recent_volume_ratio_max"] = frame["volume_ratio"].rolling(
        volume_confirmation_window,
        min_periods=volume_confirmation_window,
    ).max()
    frame["prev_close"] = frame["close"].shift(1)
    frame["prev_rsi"] = frame["rsi"].shift(1)

    frame["ema_fast"] = frame["close"].ewm(
        span=ema_fast, adjust=False, min_periods=ema_fast
    ).mean()
    frame["ema_slow"] = frame["close"].ewm(
        span=ema_slow, adjust=False, min_periods=ema_slow
    ).mean()
    frame["prev_ema_fast"] = frame["ema_fast"].shift(1)
    frame["ema_fast_slope"] = frame["ema_fast"].diff()
    frame["macd"] = frame["ema_fast"] - frame["ema_slow"]
    frame["macd_signal"] = frame["macd"].ewm(
        span=macd_signal, adjust=False, min_periods=macd_signal
    ).mean()
    # Chinese brokerage charts conventionally display the MACD histogram as
    # 2 * (DIF - DEA). The factor does not change crossings, but keeps the
    # audit chart and configured strategy on the same visual convention.
    frame["macd_hist"] = 2.0 * (frame["macd"] - frame["macd_signal"])
    frame["prev_macd_hist"] = frame["macd_hist"].shift(1)
    frame["macd_hist_delta"] = frame["macd_hist"].diff()
    frame["prev_macd_hist_delta"] = frame["macd_hist_delta"].shift(1)
    direction = np.sign(frame["macd_hist_delta"].fillna(0.0))
    direction_group = direction.ne(direction.shift()).cumsum()
    frame["macd_hist_rising_bars"] = (
        direction.eq(1).groupby(direction_group).cumsum().where(
            direction.eq(1), 0
        )
    )
    frame["macd_hist_falling_bars"] = (
        direction.eq(-1).groupby(direction_group).cumsum().where(
            direction.eq(-1), 0
        )
    )

    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - frame["prev_close"]).abs(),
            (frame["low"] - frame["prev_close"]).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.ewm(
        alpha=1 / atr_window, adjust=False, min_periods=atr_window
    ).mean()
    frame["trend_strength_atr"] = (
        (frame["ema_fast"] - frame["ema_slow"]).abs()
        / frame["atr"].replace(0, np.nan)
    )
    frame["ema_deviation_atr"] = (
        (frame["close"] - frame["ema_slow"])
        / frame["atr"].replace(0, np.nan)
    )

    # Medium-horizon state is session-local.  Prior-session warm-up may seed
    # continuous indicators, but must never leak yesterday's close/range into
    # an intraday trend or opportunity gate.
    grouped = frame.groupby("_trade_day", sort=False)
    frame["medium_return_fast"] = grouped["close"].transform(
        lambda values: values.pct_change(
            periods=medium_trend_fast_bars, fill_method=None
        )
    )
    frame["medium_return_slow"] = grouped["close"].transform(
        lambda values: values.pct_change(
            periods=medium_trend_slow_bars, fill_method=None
        )
    )
    range_window = medium_trend_fast_bars + 1
    recent_high = grouped["high"].transform(
        lambda values: values.rolling(
            range_window, min_periods=range_window
        ).max()
    )
    recent_low = grouped["low"].transform(
        lambda values: values.rolling(
            range_window, min_periods=range_window
        ).min()
    )
    frame["medium_recent_range"] = (
        recent_high / recent_low.replace(0, np.nan) - 1.0
    )

    bar_range = (frame["high"] - frame["low"]).replace(0, np.nan)
    frame["body_ratio"] = (frame["close"] - frame["open"]).abs() / bar_range
    frame["lower_wick_ratio"] = (
        frame[["open", "close"]].min(axis=1) - frame["low"]
    ) / bar_range
    frame["upper_wick_ratio"] = (
        frame["high"] - frame[["open", "close"]].max(axis=1)
    ) / bar_range

    _attach_intraday_reversal_features(
        frame,
        panic_window_bars=panic_window_bars,
        panic_return_threshold=panic_return_threshold,
        panic_volume_ratio=panic_volume_ratio,
        macd_divergence_lookback=macd_divergence_lookback,
        rebound_confirmation_bars=rebound_confirmation_bars,
        rebound_recovery_ratio=rebound_recovery_ratio,
        regime_slope_bars=regime_slope_bars,
    )

    frame["opening_range_high"] = np.nan
    frame["opening_range_low"] = np.nan
    session_position = frame.groupby("_trade_day").cumcount()
    eligible = session_position >= opening_range_bars
    opening_high = frame.groupby("_trade_day")["high"].transform(
        lambda values: values.iloc[:opening_range_bars].max()
    )
    opening_low = frame.groupby("_trade_day")["low"].transform(
        lambda values: values.iloc[:opening_range_bars].min()
    )
    frame.loc[eligible, "opening_range_high"] = opening_high[eligible]
    frame.loc[eligible, "opening_range_low"] = opening_low[eligible]
    opening_width = frame["opening_range_high"] - frame["opening_range_low"]
    frame["opening_range_position"] = (
        (frame["close"] - frame["opening_range_low"])
        / opening_width.replace(0, np.nan)
    )
    return frame


def feature_snapshot(row: pd.Series) -> dict[str, float | None]:
    fields = (
        "zscore",
        "rsi",
        "vwap",
        "vwap_deviation",
        "range_position",
        "volume_ratio",
        "ema_fast",
        "ema_slow",
        "ema_fast_slope",
        "macd",
        "macd_signal",
        "macd_hist",
        "macd_hist_delta",
        "prev_macd_hist_delta",
        "macd_hist_rising_bars",
        "macd_hist_falling_bars",
        "ema_deviation_atr",
        "atr",
        "trend_strength_atr",
        "body_ratio",
        "lower_wick_ratio",
        "upper_wick_ratio",
        "opening_range_high",
        "opening_range_low",
        "opening_range_position",
        "relative_volume_tod",
        "volume_tod_history_days",
        "benchmark_return",
        "rolling_market_beta",
        "market_residual_return",
        "market_residual_zscore",
        "daily_trend",
        "higher_timeframe_trend",
        "pullback_distance_atr",
        "recent_volume_ratio_max",
        "ema_slow_slope_window",
        "vwap_slope_window",
        "bearish_regime",
        "bullish_regime",
        "panic_window_return",
        "panic_volume_ratio",
        "recent_bearish_shock",
        "recent_bullish_shock",
        "recent_panic_volume_ratio_max",
        "bullish_macd_divergence",
        "bearish_macd_divergence",
        "bullish_divergence_recent",
        "bearish_divergence_recent",
        "bullish_bar_streak",
        "bearish_bar_streak",
        "bullish_rebound_recovery",
        "bearish_rebound_recovery",
        "bullish_rebound_structure",
        "bearish_rebound_structure",
        "recent_min_ema_deviation_atr",
        "recent_max_ema_deviation_atr",
        "bullish_reversal_evidence_score",
        "bearish_reversal_evidence_score",
        "medium_return_fast",
        "medium_return_slow",
        "medium_recent_range",
    )
    result: dict[str, float | None] = {}
    for field in fields:
        value = row.get(field)
        result[field] = None if pd.isna(value) else round(float(value), 6)
    return result


def _context_frame(
    bars: list[dict[str, Any]], required: tuple[str, ...]
) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame(columns=("date", *required))
    frame = pd.DataFrame(bars).copy()
    if "date" not in frame:
        return pd.DataFrame(columns=("date", *required))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    for column in required:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    return (
        frame.dropna(subset=["date", *required])
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )


def attach_strategy_context(
    frame: pd.DataFrame,
    *,
    historical_bars: list[dict[str, Any]] | None = None,
    benchmark_bars: list[dict[str, Any]] | None = None,
    daily_bars: list[dict[str, Any]] | None = None,
    higher_timeframe_bars: list[dict[str, Any]] | None = None,
    market_beta_window: int = 20,
    higher_ema_fast: int = 5,
    higher_ema_slow: int = 10,
    daily_trend_window: int = 20,
) -> pd.DataFrame:
    """Attach only as-of context features; target rows are never backfilled."""
    result = frame.copy()
    local_time = result["date"].dt.tz_convert("Asia/Shanghai")
    result["_minute_key"] = local_time.dt.strftime("%H:%M")

    history = _context_frame(historical_bars or [], ("volume",))
    if not history.empty:
        history["_minute_key"] = history["date"].dt.tz_convert(
            "Asia/Shanghai"
        ).dt.strftime("%H:%M")
        history["_trade_day"] = history["date"].dt.tz_convert(
            "Asia/Shanghai"
        ).dt.date
        baselines = history.groupby("_minute_key").agg(
            _volume_tod_median=("volume", "median"),
            volume_tod_history_days=("_trade_day", "nunique"),
        )
        result = result.join(baselines, on="_minute_key")
        result["relative_volume_tod"] = (
            result["volume"]
            / result["_volume_tod_median"].replace(0, np.nan)
        )
        result.drop(columns=["_volume_tod_median"], inplace=True)
    else:
        result["relative_volume_tod"] = np.nan
        result["volume_tod_history_days"] = 0.0

    benchmark = _context_frame(benchmark_bars or [], ("close",))
    if not benchmark.empty:
        benchmark["benchmark_return"] = benchmark["close"].pct_change()
        benchmark_returns = benchmark.set_index("date")["benchmark_return"]
        result["benchmark_return"] = result["date"].map(benchmark_returns)
        stock_return = result["return_1"]
        market_return = result["benchmark_return"]
        result["rolling_market_beta"] = (
            stock_return.rolling(
                market_beta_window, min_periods=market_beta_window
            ).cov(market_return)
            / market_return.rolling(
                market_beta_window, min_periods=market_beta_window
            ).var()
        )
        result["market_residual_return"] = (
            stock_return
            - result["rolling_market_beta"] * market_return
        )
        residual = result["market_residual_return"]
        residual_mean = residual.rolling(
            market_beta_window, min_periods=market_beta_window
        ).mean()
        residual_std = residual.rolling(
            market_beta_window, min_periods=market_beta_window
        ).std(ddof=0)
        result["market_residual_zscore"] = (
            (residual - residual_mean) / residual_std.replace(0, np.nan)
        )
    else:
        for column in (
            "benchmark_return",
            "rolling_market_beta",
            "market_residual_return",
            "market_residual_zscore",
        ):
            result[column] = np.nan

    daily = _context_frame(daily_bars or [], ("close",))
    if len(daily) >= daily_trend_window:
        daily_fast = daily["close"].ewm(
            span=max(2, daily_trend_window // 4),
            adjust=False,
            min_periods=max(2, daily_trend_window // 4),
        ).mean()
        daily_slow = daily["close"].ewm(
            span=daily_trend_window,
            adjust=False,
            min_periods=daily_trend_window,
        ).mean()
        latest_fast = daily_fast.iloc[-1]
        latest_slow = daily_slow.iloc[-1]
        result["daily_trend"] = (
            1.0
            if latest_fast > latest_slow
            else -1.0 if latest_fast < latest_slow else 0.0
        )
    else:
        result["daily_trend"] = np.nan

    higher = _context_frame(higher_timeframe_bars or [], ("close",))
    if not higher.empty:
        higher["_higher_fast"] = higher["close"].ewm(
            span=higher_ema_fast,
            adjust=False,
            min_periods=higher_ema_fast,
        ).mean()
        higher["_higher_slow"] = higher["close"].ewm(
            span=higher_ema_slow,
            adjust=False,
            min_periods=higher_ema_slow,
        ).mean()
        higher["higher_timeframe_trend"] = np.sign(
            higher["_higher_fast"] - higher["_higher_slow"]
        )
        target = result.sort_values("date")
        merged = pd.merge_asof(
            target[["date"]],
            higher[["date", "higher_timeframe_trend"]],
            on="date",
            direction="backward",
            allow_exact_matches=True,
        )
        result.loc[target.index, "higher_timeframe_trend"] = (
            merged["higher_timeframe_trend"].to_numpy()
        )
    else:
        result["higher_timeframe_trend"] = np.nan

    result["pullback_distance_atr"] = (
        pd.concat(
            [
                (result["close"] - result["ema_fast"]).abs(),
                (result["close"] - result["vwap"]).abs(),
            ],
            axis=1,
        ).min(axis=1)
        / result["atr"].replace(0, np.nan)
    )
    result.drop(columns=["_minute_key"], inplace=True)
    return result

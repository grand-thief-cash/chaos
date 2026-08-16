from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


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

    bar_range = (frame["high"] - frame["low"]).replace(0, np.nan)
    frame["body_ratio"] = (frame["close"] - frame["open"]).abs() / bar_range
    frame["lower_wick_ratio"] = (
        frame[["open", "close"]].min(axis=1) - frame["low"]
    ) / bar_range
    frame["upper_wick_ratio"] = (
        frame["high"] - frame[["open", "close"]].max(axis=1)
    ) / bar_range

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

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


def build_causal_features(bars: list[dict[str, Any]], window: int) -> pd.DataFrame:
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
    cumulative_volume = frame["volume"].clip(lower=0).cumsum()
    frame["vwap"] = (amount.clip(lower=0).cumsum() / cumulative_volume.replace(0, np.nan)).fillna(frame["close"])
    frame["vwap_deviation"] = frame["close"] / frame["vwap"] - 1

    rolling_high = frame["high"].rolling(window, min_periods=window).max()
    rolling_low = frame["low"].rolling(window, min_periods=window).min()
    frame["range_position"] = (frame["close"] - rolling_low) / (rolling_high - rolling_low).replace(0, np.nan)
    frame["volume_median"] = frame["volume"].rolling(window, min_periods=window).median()
    frame["volume_ratio"] = frame["volume"] / frame["volume_median"].replace(0, np.nan)
    frame["prev_close"] = frame["close"].shift(1)
    frame["prev_rsi"] = frame["rsi"].shift(1)
    return frame


def feature_snapshot(row: pd.Series) -> dict[str, float | None]:
    fields = ("zscore", "rsi", "vwap", "vwap_deviation", "range_position", "volume_ratio")
    result: dict[str, float | None] = {}
    for field in fields:
        value = row.get(field)
        result[field] = None if pd.isna(value) else round(float(value), 6)
    return result

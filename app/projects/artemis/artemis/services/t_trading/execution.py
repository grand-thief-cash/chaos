from __future__ import annotations

from typing import Any

import pandas as pd

from artemis.models.t_trading import TExecutionConfig, TStrategyConfig


def _fees(side: str, value: float, config: TExecutionConfig) -> dict[str, float]:
    commission = max(config.minimum_commission, value * config.commission_rate)
    stamp_duty = value * config.stamp_duty_rate_on_sell if side == "SELL" else 0.0
    transfer_fee = value * config.transfer_fee_rate
    return {
        "commission": round(commission, 4),
        "stamp_duty": round(stamp_duty, 4),
        "transfer_fee": round(transfer_fee, 4),
        "total_fee": round(commission + stamp_duty + transfer_fee, 4),
    }


def simulate_fills(
    frame: pd.DataFrame,
    signals: list[dict[str, Any]],
    config: TExecutionConfig,
) -> list[dict[str, Any]]:
    fills: list[dict[str, Any]] = []
    for signal in signals:
        fill_index = signal["bar_index"] + 1
        if fill_index >= len(frame):
            continue
        row = frame.iloc[fill_index]
        raw_price = float(row["open"])
        multiplier = 1 + config.slippage_bps / 10000 if signal["side"] == "BUY" else 1 - config.slippage_bps / 10000
        fill_price = round(raw_price * multiplier, 4)
        value = fill_price * config.quantity
        fill = {
            "fill_id": f"fill-{len(fills) + 1:03d}",
            "signal_id": signal["signal_id"],
            "bar_index": fill_index,
            "fill_time": row["date"].isoformat(),
            "side": signal["side"],
            "quantity": config.quantity,
            "raw_open_price": round(raw_price, 4),
            "fill_price": fill_price,
            "notional": round(value, 2),
            "slippage_cost": round(abs(fill_price - raw_price) * config.quantity, 4),
        }
        fill.update(_fees(signal["side"], value, config))
        fills.append(fill)
    return fills


def pair_round_trips(
    frame: pd.DataFrame,
    fills: list[dict[str, Any]],
    strategy: TStrategyConfig,
) -> list[dict[str, Any]]:
    first_side = "BUY" if strategy.direction == "buy_first" else "SELL"
    second_side = "SELL" if first_side == "BUY" else "BUY"
    trips: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    for fill in fills:
        if pending is None:
            if fill["side"] == first_side:
                pending = fill
            continue
        if fill["side"] != second_side:
            continue

        buy = pending if pending["side"] == "BUY" else fill
        sell = pending if pending["side"] == "SELL" else fill
        quantity = min(buy["quantity"], sell["quantity"])
        gross_pnl = (sell["fill_price"] - buy["fill_price"]) * quantity
        total_fee = buy["total_fee"] + sell["total_fee"]
        net_pnl = gross_pnl - total_fee
        segment = frame.iloc[pending["bar_index"] : fill["bar_index"] + 1]
        if first_side == "BUY":
            mfe = (float(segment["high"].max()) - pending["fill_price"]) * quantity
            mae = (float(segment["low"].min()) - pending["fill_price"]) * quantity
        else:
            mfe = (pending["fill_price"] - float(segment["low"].min())) * quantity
            mae = (pending["fill_price"] - float(segment["high"].max())) * quantity
        base_notional = max(pending["notional"], 0.01)
        trips.append(
            {
                "round_trip_id": f"trip-{len(trips) + 1:03d}",
                "open_fill_id": pending["fill_id"],
                "close_fill_id": fill["fill_id"],
                "direction": strategy.direction,
                "open_time": pending["fill_time"],
                "close_time": fill["fill_time"],
                "quantity": quantity,
                "gross_pnl": round(gross_pnl, 4),
                "total_fee": round(total_fee, 4),
                "net_pnl": round(net_pnl, 4),
                "return_pct": round(net_pnl / base_notional * 100, 6),
                "mfe": round(mfe, 4),
                "mae": round(mae, 4),
                "win": net_pnl > 0,
            }
        )
        pending = None
    return trips

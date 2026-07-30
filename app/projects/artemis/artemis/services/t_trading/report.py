from __future__ import annotations

from typing import Any


def summarize_round_trips(round_trips: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(round_trips)
    wins = sum(1 for trip in round_trips if trip["win"])
    gross_pnl = sum(float(trip["gross_pnl"]) for trip in round_trips)
    total_fee = sum(float(trip["total_fee"]) for trip in round_trips)
    net_pnl = sum(float(trip["net_pnl"]) for trip in round_trips)
    returns = [float(trip["return_pct"]) for trip in round_trips]
    gross_profit = sum(max(float(trip["net_pnl"]), 0.0) for trip in round_trips)
    gross_loss = sum(min(float(trip["net_pnl"]), 0.0) for trip in round_trips)
    return {
        "round_trips": count,
        "wins": wins,
        "losses": count - wins,
        "win_rate": round(wins / count, 6) if count else 0.0,
        "gross_pnl": round(gross_pnl, 4),
        "total_fee": round(total_fee, 4),
        "net_pnl": round(net_pnl, 4),
        "profit_factor": round(gross_profit / abs(gross_loss), 6) if gross_loss < 0 else None,
        "average_return_pct": round(sum(returns) / count, 6) if count else 0.0,
        "best_return_pct": round(max(returns), 6) if returns else 0.0,
        "worst_return_pct": round(min(returns), 6) if returns else 0.0,
    }


def summarize_replays(results: list[dict[str, Any]]) -> dict[str, Any]:
    trips = [trip for result in results for trip in result["round_trips"]]
    summary = summarize_round_trips(trips)
    summary.update(
        {
            "replay_days": len(results),
            "days_with_trades": sum(1 for result in results if result["round_trips"]),
            "signal_count": sum(len(result["signals"]) for result in results),
            "fill_count": sum(len(result["fills"]) for result in results),
        }
    )
    return summary

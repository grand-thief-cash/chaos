from __future__ import annotations

from typing import Any, Dict


class BacktestResultNormalizer:
    """回测结果标准化器，将 Backtrader 原始输出转换为统一的 summary + artifacts 格式。"""

    @staticmethod
    def _safe_dict(value: Any) -> Dict[str, Any]:
        """安全地将值转换为字典，非字典类型返回空字典。"""
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _normalize_trade_analyzer(trade_analyzer: Dict[str, Any]) -> Dict[str, Any]:
        """从 Backtrader TradeAnalyzer 结果中提取交易统计（次数、胜率）。"""
        total = int(((trade_analyzer.get("total") or {}).get("closed") or 0))
        won = int((((trade_analyzer.get("won") or {}).get("total")) or 0))
        lost = int((((trade_analyzer.get("lost") or {}).get("total")) or 0))
        win_rate = round(float(won / total), 4) if total > 0 else 0.0
        return {
            "trade_count": total,
            "win_count": won,
            "loss_count": lost,
            "win_rate": win_rate,
        }

    @staticmethod
    def _compute_order_based_stats(orders: list) -> Dict[str, Any]:
        """从成交订单中用 FIFO 配对法计算交易统计。

        当 backtrader TradeAnalyzer 报告 0 笔交易时（例如网格策略持仓从未归零），
        使用此方法从实际成交订单中匹配买卖对，计算有意义的统计数据。

        Returns:
            {
                "trade_count": int,   # 完成的买卖配对数
                "win_count": int,
                "loss_count": int,
                "win_rate": float,
                "realized_pnl": float,  # 已配对部分的已实现盈亏
            }
        """
        completed_buys: list = []  # FIFO queue: [(size, price), ...]
        pair_count = 0
        win_count = 0
        loss_count = 0
        realized_pnl = 0.0

        for o in orders:
            if o.get("status") != "Completed":
                continue
            size = abs(float(o.get("size", 0)))
            price = float(o.get("price", 0))
            if size <= 0 or price <= 0:
                continue

            if o.get("order_type") == "BUY":
                completed_buys.append([size, price])
            elif o.get("order_type") == "SELL":
                remaining = size
                while remaining > 0 and completed_buys:
                    buy_size, buy_price = completed_buys[0]
                    match_qty = min(remaining, buy_size)
                    pnl = match_qty * (price - buy_price)
                    realized_pnl += pnl
                    pair_count += 1
                    if pnl > 0:
                        win_count += 1
                    elif pnl < 0:
                        loss_count += 1
                    remaining -= match_qty
                    completed_buys[0][0] -= match_qty
                    if completed_buys[0][0] <= 0.0001:
                        completed_buys.pop(0)

        return {
            "trade_count": pair_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(float(win_count / pair_count), 4) if pair_count > 0 else 0.0,
            "realized_pnl": round(realized_pnl, 2),
        }

    @staticmethod
    def normalize(
        *,
        run_id: int | str,
        parent_run_id: int | str | None,
        task_code: str,
        mode: str,
        strategy_code: str,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        start_cash: float,
        end_value: float,
        strategy_instance: Any,
        analyzer_results: Dict[str, Any],
        bars_processed: int,
    ) -> Dict[str, Any]:
        """标准化回测结果，返回包含 run_meta、summary 和 artifacts 的字典。"""
        returns = BacktestResultNormalizer._safe_dict(analyzer_results.get("returns"))
        drawdown = BacktestResultNormalizer._safe_dict(analyzer_results.get("drawdown"))
        trade_analyzer = BacktestResultNormalizer._safe_dict(analyzer_results.get("trade_analyzer"))
        sharpe = analyzer_results.get("sharpe")

        trade_stats = BacktestResultNormalizer._normalize_trade_analyzer(trade_analyzer)

        # 如果 TradeAnalyzer 报告 0 笔交易，尝试从订单中用 FIFO 配对法计算
        if trade_stats["trade_count"] == 0:
            orders = list(getattr(strategy_instance, "order_events", []) or [])
            order_stats = BacktestResultNormalizer._compute_order_based_stats(orders)
            if order_stats["trade_count"] > 0:
                trade_stats = {
                    "trade_count": order_stats["trade_count"],
                    "win_count": order_stats["win_count"],
                    "loss_count": order_stats["loss_count"],
                    "win_rate": order_stats["win_rate"],
                }

        max_dd = float(((drawdown.get("max") or {}).get("drawdown") or 0.0))
        pnl = round(float(end_value - start_cash), 2)
        pnl_pct = round(float((pnl / start_cash) if start_cash else 0.0), 6)

        summary = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
            "task_code": task_code,
            "mode": mode,
            "strategy_code": strategy_code,
            "symbol": symbol,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "start_cash": round(float(start_cash), 2),
            "end_value": round(float(end_value), 2),
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "max_drawdown": round(max_dd, 4),
            "sharpe": round(float(sharpe.get("sharperatio") or 0.0), 4) if isinstance(sharpe, dict) else 0.0,
            "bars_processed": int(bars_processed),
            **trade_stats,
        }

        equity_curve = list(getattr(strategy_instance, "equity_curve", []) or [])
        signals = list(getattr(strategy_instance, "signal_events", []) or [])
        orders = list(getattr(strategy_instance, "order_events", []) or [])
        trades = list(getattr(strategy_instance, "trade_events", []) or [])
        positions = list(getattr(strategy_instance, "position_curve", []) or [])
        diagnostics = list(getattr(strategy_instance, "bar_detail_events", []) or [])

        # Compute return rate curve from equity curve
        return_curve = []
        if equity_curve and start_cash > 0:
            for point in equity_curve:
                return_pct = round((point["value"] - start_cash) / start_cash, 6)
                return_curve.append({
                    "timestamp": point["timestamp"],
                    "return_pct": return_pct,
                })

        artifacts = {
            "analyzers": analyzer_results,
            "trades": trades,
            "orders": orders,
            "signals": signals,
            "equity_curve": equity_curve,
            "return_curve": return_curve,
            "positions": positions,
            "bar_details": diagnostics,
            "plot_manifest": {
                "version": "v1",
                "charts": [
                    {
                        "chart_code": "equity_overview",
                        "series": ["equity_curve", "signals"],
                        "x_axis": "timestamp",
                    },
                    {
                        "chart_code": "return_rate",
                        "series": ["return_curve"],
                        "x_axis": "timestamp",
                        "y_axis": "percentage",
                    },
                ],
            },
            "plot_series": {
                "equity_curve": equity_curve,
                "return_curve": return_curve,
                "signals": signals,
                "positions": positions,
            },
        }
        return {
            "run_meta": {
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
                "task_code": task_code,
            },
            "summary": summary,
            "artifacts": artifacts,
        }


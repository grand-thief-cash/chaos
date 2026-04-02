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
        win_rate = float(won / total) if total > 0 else 0.0
        return {
            "trade_count": total,
            "win_count": won,
            "loss_count": lost,
            "win_rate": win_rate,
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
        timeframe: str,
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
        max_dd = float(((drawdown.get("max") or {}).get("drawdown") or 0.0))
        pnl = float(end_value - start_cash)
        pnl_pct = float((pnl / start_cash) if start_cash else 0.0)

        summary = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
            "task_code": task_code,
            "mode": mode,
            "strategy_code": strategy_code,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "start_cash": float(start_cash),
            "end_value": float(end_value),
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "max_drawdown": max_dd,
            "sharpe": float(sharpe.get("sharperatio") or 0.0) if isinstance(sharpe, dict) else 0.0,
            "bars_processed": int(bars_processed),
            **trade_stats,
        }

        equity_curve = list(getattr(strategy_instance, "equity_curve", []) or [])
        signals = list(getattr(strategy_instance, "signal_events", []) or [])
        orders = list(getattr(strategy_instance, "order_events", []) or [])
        trades = list(getattr(strategy_instance, "trade_events", []) or [])
        positions = list(getattr(strategy_instance, "position_curve", []) or [])

        artifacts = {
            "analyzers": analyzer_results,
            "trades": trades,
            "orders": orders,
            "signals": signals,
            "equity_curve": equity_curve,
            "positions": positions,
            "plot_manifest": {
                "version": "v1",
                "charts": [
                    {
                        "chart_code": "equity_overview",
                        "series": ["equity_curve", "signals"],
                        "x_axis": "timestamp",
                    }
                ],
            },
            "plot_series": {
                "equity_curve": equity_curve,
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


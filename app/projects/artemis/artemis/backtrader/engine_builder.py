from __future__ import annotations

from typing import Any, Dict, cast

import backtrader as bt
import pandas as pd

from artemis.backtrader.analyzer_profile_registry import AnalyzerProfileSpec
from artemis.backtrader.strategy_registry import StrategySpec


class BacktraderEngineBuilder:
    @staticmethod
    def dataframe_to_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
        feed_df = cast(pd.DataFrame, cast(object, df.copy(deep=True)))
        if "date" not in feed_df.columns:
            raise ValueError("bars dataframe missing 'date' column")
        feed_df["date"] = pd.to_datetime(cast(Any, feed_df["date"]), errors="coerce")
        feed_df = cast(pd.DataFrame, feed_df.dropna(subset=["date"]).sort_values("date").set_index("date"))

        for col in ["open", "high", "low", "close", "volume"]:
            if col in feed_df.columns:
                feed_df[col] = pd.to_numeric(feed_df[col], errors="coerce")

        if "openinterest" not in feed_df.columns:
            feed_df["openinterest"] = 0
        return bt.feeds.PandasData(dataname=feed_df)  # type: ignore[call-arg]

    @staticmethod
    def build(
        *,
        df: pd.DataFrame,
        strategy_spec: StrategySpec,
        strategy_params: Dict[str, Any],
        analyzer_profile: AnalyzerProfileSpec,
        cash: float,
        commission: float,
    ) -> bt.Cerebro:
        cerebro = bt.Cerebro(stdstats=False)  # type: ignore[call-arg]
        cerebro.broker.setcash(float(cash))
        cerebro.broker.setcommission(commission=float(commission))
        cerebro.adddata(BacktraderEngineBuilder.dataframe_to_feed(df))
        cerebro.addstrategy(strategy_spec.cls, **strategy_params)

        for analyzer_name, analyzer_cls, analyzer_kwargs in analyzer_profile.analyzers:
            cerebro.addanalyzer(analyzer_cls, _name=analyzer_name, **dict(analyzer_kwargs or {}))

        for _, observer_cls, observer_kwargs in analyzer_profile.observers:
            cerebro.addobserver(observer_cls, **dict(observer_kwargs or {}))

        return cerebro


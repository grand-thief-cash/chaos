from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import requests

from artemis.services.t_trading.live_quotes import (
    QuoteBookLevel,
    QuotePoint,
)


CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
_SINA_LINE = re.compile(
    r'var\s+hq_str_([A-Za-z0-9_]+)="(.*?)";',
    flags=re.DOTALL,
)
_NORMALIZED_SYMBOL = re.compile(r"^(sh|sz|bj)(\d{6})$")


class RealtimeQuoteAdapterError(RuntimeError):
    """A provider response cannot be safely converted into quote points."""


class RealtimeQuoteAdapter(Protocol):
    provider: str

    def fetch(self, symbols: Sequence[str]) -> list[QuotePoint]:
        """Fetch one point per symbol or fail without returning partial data."""


def normalize_a_share_symbol(symbol: str) -> str:
    compact = symbol.strip().lower()
    matched = _NORMALIZED_SYMBOL.fullmatch(compact)
    if matched:
        return compact
    prefix_style = re.fullmatch(r"(sh|sz|bj)[.]?(\d{6})", compact)
    if prefix_style:
        return f"{prefix_style.group(1)}{prefix_style.group(2)}"
    suffix_style = re.fullmatch(r"(\d{6})[.]?(sh|sz|bj)", compact)
    if suffix_style:
        return f"{suffix_style.group(2)}{suffix_style.group(1)}"
    if not re.fullmatch(r"\d{6}", compact):
        raise ValueError(
            "symbol must be six digits or use an sh/sz/bj prefix"
        )
    if compact[0] in {"5", "6", "9"}:
        return f"sh{compact}"
    if compact[0] in {"0", "1", "2", "3"}:
        return f"sz{compact}"
    if compact[0] in {"4", "8"}:
        return f"bj{compact}"
    raise ValueError(f"cannot infer exchange for symbol: {symbol}")


def _required_float(value: str, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RealtimeQuoteAdapterError(
            f"invalid Sina {field_name}: {value!r}"
        ) from exc
    if parsed <= 0:
        raise RealtimeQuoteAdapterError(
            f"Sina {field_name} is not positive: {value!r}"
        )
    return parsed


def _optional_positive_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _non_negative_float(value: str, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RealtimeQuoteAdapterError(
            f"invalid Sina {field_name}: {value!r}"
        ) from exc
    if parsed < 0:
        raise RealtimeQuoteAdapterError(
            f"Sina {field_name} is negative: {value!r}"
        )
    return parsed


def _parse_source_time(trade_date: str, trade_time: str) -> datetime:
    try:
        parsed = datetime.strptime(
            f"{trade_date} {trade_time}", "%Y-%m-%d %H:%M:%S"
        )
    except ValueError as exc:
        raise RealtimeQuoteAdapterError(
            f"invalid Sina exchange time: {trade_date!r} {trade_time!r}"
        ) from exc
    return parsed.replace(tzinfo=CHINA_TZ)


def _parse_book_level(
    values: list[str], volume_index: int, price_index: int
) -> QuoteBookLevel | None:
    price = _optional_positive_float(values[price_index])
    if price is None:
        return None
    volume = _non_negative_float(
        values[volume_index],
        field_name=f"book_volume_{volume_index}",
    )
    return QuoteBookLevel(price=price, volume=volume)


class SinaRealtimeQuoteAdapter:
    """Adapter for the quote endpoint used by Sina's real-stock page.

    The endpoint is an observed, undocumented web interface. Callers must apply
    their own authorization, licensing, throttling, retry and monitoring policy.
    """

    provider = "sina"
    endpoint = "https://hq.sinajs.cn/"
    referer = "https://finance.sina.com.cn/realstock/"

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout_seconds: float = 3.0,
        clock: Callable[[], datetime] | None = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(CHINA_TZ))

    def fetch(self, symbols: Sequence[str]) -> list[QuotePoint]:
        normalized = [normalize_a_share_symbol(symbol) for symbol in symbols]
        if not normalized:
            raise ValueError("symbols must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("symbols must not contain duplicates")

        observed_at = self._clock()
        if observed_at.tzinfo is None:
            raise ValueError("adapter clock must return a timezone-aware time")
        response = self._session.get(
            self.endpoint,
            params={
                "rn": str(int(observed_at.timestamp() * 1000)),
                "list": ",".join(normalized),
            },
            headers={
                "Referer": self.referer,
                "User-Agent": (
                    "Mozilla/5.0 (compatible; ArtemisQuoteAdapter/1.0)"
                ),
                "Accept": "*/*",
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        try:
            body = response.content.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise RealtimeQuoteAdapterError(
                "Sina response is not valid GB18030"
            ) from exc
        return self.parse_response(
            body,
            requested_symbols=normalized,
            observed_at=observed_at,
        )

    @staticmethod
    def parse_response(
        body: str,
        *,
        requested_symbols: Sequence[str],
        observed_at: datetime,
    ) -> list[QuotePoint]:
        if observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        payloads = {
            matched.group(1): matched.group(2)
            for matched in _SINA_LINE.finditer(body)
        }
        points: list[QuotePoint] = []
        missing: list[str] = []
        for symbol in requested_symbols:
            payload = payloads.get(symbol)
            if not payload:
                missing.append(symbol)
                continue
            values = payload.split(",")
            if len(values) < 33:
                raise RealtimeQuoteAdapterError(
                    f"Sina payload for {symbol} has {len(values)} fields; "
                    "expected at least 33"
                )
            bids = tuple(
                level
                for offset in range(5)
                if (
                    level := _parse_book_level(
                        values,
                        volume_index=10 + offset * 2,
                        price_index=11 + offset * 2,
                    )
                )
                is not None
            )
            asks = tuple(
                level
                for offset in range(5)
                if (
                    level := _parse_book_level(
                        values,
                        volume_index=20 + offset * 2,
                        price_index=21 + offset * 2,
                    )
                )
                is not None
            )
            point = QuotePoint(
                observed_at=observed_at,
                source_time=_parse_source_time(values[30], values[31]),
                source="sina",
                symbol=symbol,
                name=values[0],
                price=_required_float(values[3], field_name="current_price"),
                cumulative_volume=_non_negative_float(
                    values[8], field_name="cumulative_volume"
                ),
                cumulative_amount=_non_negative_float(
                    values[9], field_name="cumulative_amount"
                ),
                open=_optional_positive_float(values[1]),
                previous_close=_optional_positive_float(values[2]),
                day_high=_optional_positive_float(values[4]),
                day_low=_optional_positive_float(values[5]),
                bids=bids,
                asks=asks,
                status=values[32],
            )
            point.validate()
            points.append(point)
        if missing:
            raise RealtimeQuoteAdapterError(
                "Sina response is missing requested symbols: "
                + ", ".join(missing)
            )
        return points


def create_realtime_quote_adapter(
    provider: str, **kwargs: Any
) -> RealtimeQuoteAdapter:
    normalized = provider.strip().lower()
    if normalized == "sina":
        return SinaRealtimeQuoteAdapter(**kwargs)
    raise ValueError(
        f"unsupported real-time quote provider: {provider}; "
        "currently available: sina"
    )

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from artemis.services.t_trading.realtime_adapters import (
    RealtimeQuoteAdapterError,
    SinaRealtimeQuoteAdapter,
    create_realtime_quote_adapter,
    normalize_a_share_symbol,
)


SHANGHAI = timezone(timedelta(hours=8))
OBSERVED_AT = datetime(2026, 7, 30, 11, 14, 57, tzinfo=SHANGHAI)
SINA_RESPONSE = (
    'var hq_str_sh600183="生益科技,105.000,108.180,98.340,108.830,'
    "98.300,98.340,98.370,45650221,4706854523.000,100,98.340,"
    "1200,98.330,100,98.320,800,98.310,2000,98.300,2700,98.370,"
    "1000,98.380,6200,98.400,100,98.410,1500,98.420,2026-07-30,"
    '11:14:56,00,";'
)


class _FakeResponse:
    def __init__(self, body: str):
        self.content = body.encode("gb18030")
        self.status_checked = False

    def raise_for_status(self) -> None:
        self.status_checked = True


class _FakeSession:
    def __init__(self, body: str):
        self.response = _FakeResponse(body)
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_sina_adapter_decodes_observed_page_payload_and_order_book():
    session = _FakeSession(SINA_RESPONSE)
    adapter = SinaRealtimeQuoteAdapter(
        session=session,
        clock=lambda: OBSERVED_AT,
    )

    points = adapter.fetch(["600183"])

    assert len(points) == 1
    point = points[0]
    assert point.symbol == "sh600183"
    assert point.name == "生益科技"
    assert point.price == 98.34
    assert point.previous_close == 108.18
    assert point.cumulative_volume == 45_650_221
    assert point.cumulative_amount == 4_706_854_523
    assert point.source_time.isoformat() == "2026-07-30T11:14:56+08:00"
    assert len(point.bids) == 5
    assert point.bids[0].price == 98.34
    assert point.bids[0].volume == 100
    assert point.asks[0].price == 98.37
    assert point.asks[0].volume == 2700
    assert point.status == "00"

    call = session.calls[0]
    assert call["url"] == "https://hq.sinajs.cn/"
    assert call["params"]["list"] == "sh600183"
    assert call["headers"]["Referer"].startswith(
        "https://finance.sina.com.cn/"
    )
    assert call["timeout"] == 3.0
    assert session.response.status_checked is True


def test_sina_adapter_fails_closed_for_missing_or_short_payload():
    with pytest.raises(RealtimeQuoteAdapterError, match="missing"):
        SinaRealtimeQuoteAdapter.parse_response(
            'var hq_str_sh600183="";',
            requested_symbols=["sh600183"],
            observed_at=OBSERVED_AT,
        )

    with pytest.raises(RealtimeQuoteAdapterError, match="expected at least 33"):
        SinaRealtimeQuoteAdapter.parse_response(
            'var hq_str_sh600183="name,1,2,3";',
            requested_symbols=["sh600183"],
            observed_at=OBSERVED_AT,
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("sh600183", "sh600183"),
        ("SH600183", "sh600183"),
        ("600183.SH", "sh600183"),
        ("sz.000001", "sz000001"),
        ("600183", "sh600183"),
        ("000001", "sz000001"),
        ("830799", "bj830799"),
    ],
)
def test_symbol_normalization(raw: str, expected: str):
    assert normalize_a_share_symbol(raw) == expected


def test_adapter_factory_has_explicit_provider_boundary():
    assert isinstance(
        create_realtime_quote_adapter(
            "sina",
            session=_FakeSession(SINA_RESPONSE),
            clock=lambda: OBSERVED_AT,
        ),
        SinaRealtimeQuoteAdapter,
    )
    with pytest.raises(ValueError, match="currently available: sina"):
        create_realtime_quote_adapter("tencent")

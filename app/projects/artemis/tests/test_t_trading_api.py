from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from artemis.api.http_gateway.workbench_routes import router


def _bars() -> list[dict]:
    prices = [
        10.00, 10.02, 10.01, 10.03, 10.02, 10.01, 10.00, 9.99, 9.98, 9.97,
        9.90, 9.82, 9.74, 9.68, 9.62, 9.66, 9.72, 9.80, 9.90, 10.02,
        10.14, 10.25, 10.36, 10.43, 10.49, 10.44, 10.36, 10.29, 10.24, 10.20,
    ]
    start = datetime(2026, 7, 1, 9, 35, tzinfo=timezone(timedelta(hours=8)))
    bars = []
    previous = prices[0]
    for index, close in enumerate(prices):
        volume = 10000 + index * 100
        bars.append(
            {
                "date": (start + timedelta(minutes=index * 5)).isoformat(),
                "open": previous,
                "high": max(previous, close) + 0.02,
                "low": min(previous, close) - 0.02,
                "close": close,
                "volume": volume,
                "amount": close * volume,
            }
        )
        previous = close
    return bars


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _payload() -> dict:
    return {
        "security_id": 1,
        "trade_date": "2026-07-01",
        "period": "min5",
        "adjust": "nf",
        "persistence_mode": "ephemeral",
        "strategy": {
            "direction": "buy_first",
            "window": 5,
            "entry_z": 0.5,
            "exit_z": 0.5,
            "entry_rsi": 50,
            "exit_rsi": 50,
            "confirmation_bars": 4,
            "cooldown_bars": 0,
            "max_round_trips": 2,
        },
        "execution": {
            "quantity": 100,
            "commission_rate": 0.0003,
            "minimum_commission": 5,
            "stamp_duty_rate_on_sell": 0.0005,
            "transfer_fee_rate": 0.00001,
            "slippage_bps": 1,
        },
    }


def test_replay_http_flow_returns_review_payload(monkeypatch):
    def fake_market_data(**_kwargs):
        return {"security_id": 1, "symbol": "sh.600000", "period": "min5", "bars": _bars()}

    monkeypatch.setattr("artemis.services.workbench.get_market_bars", fake_market_data)
    response = _client().post("/workbench/t-trading/replay", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["run_meta"]["persistence_mode"] == "ephemeral"
    assert body["run_meta"]["symbol"] == "sh.600000"
    assert body["bars"]
    assert body["signals"]
    assert body["fills"]
    assert body["fills"][0]["bar_index"] == body["signals"][0]["bar_index"] + 1
    assert body["summary"]["round_trips"] >= 1


def test_persistent_backtest_mode_is_rejected_at_http_boundary():
    payload = _payload()
    payload["persistence_mode"] = "persistent"
    response = _client().post("/workbench/t-trading/replay", json=payload)
    assert response.status_code == 422


def test_config_advertises_ephemeral_as_only_mode():
    response = _client().get("/workbench/t-trading/config")
    assert response.status_code == 200
    assert response.json()["persistence_modes"] == ["ephemeral"]
    assert response.json()["periods"] == ["min5"]
    assert response.json()["result_storage"] == "none"


def test_batch_http_flow_returns_summary_only_and_isolates_payload(monkeypatch):
    def fake_market_data(**_kwargs):
        return {"security_id": 1, "symbol": "sh.600000", "period": "min5", "bars": _bars()}

    monkeypatch.setattr("artemis.services.workbench.get_market_bars", fake_market_data)
    replay = _payload()
    payload = {
        "security_ids": [1],
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "period": "min5",
        "adjust": "nf",
        "persistence_mode": "ephemeral",
        "strategy": replay["strategy"],
        "execution": replay["execution"],
    }
    response = _client().post("/workbench/t-trading/batch", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["replay_days"] == 1
    assert body["failures"] == []
    assert body["by_day"][0]["trade_date"] == "2026-07-01"
    assert "bars" not in body["results"][0]

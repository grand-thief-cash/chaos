import asyncio

import pytest

from atlas.core.llm import KeyPool
from atlas.core.sample_task_registry import SampleTaskRegistry, sample_identity_key
from atlas.models import LLMAPIKeyCfg


def test_identity_key_is_order_invariant_over_report_types():
    a = sample_identity_key(120, ["stock", "macro"], "2026-01-01", None)
    b = sample_identity_key(120, ["macro", "stock"], "2026-01-01", None)
    assert a == b


def test_identity_key_distinguishes_different_sample_size():
    a = sample_identity_key(120, ["stock"], None, None)
    b = sample_identity_key(200, ["stock"], None, None)
    assert a != b


@pytest.mark.asyncio
async def test_key_pool_caps_per_key_concurrency():
    # Two keys, each capped at 1; total in-flight must never exceed 2.
    pool = KeyPool([
        LLMAPIKeyCfg(key="k1", max_concurrency=1),
        LLMAPIKeyCfg(key="k2", max_concurrency=1),
    ])
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def worker():
        nonlocal in_flight, peak
        async with pool.acquire():
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            async with lock:
                in_flight -= 1

    await asyncio.gather(*(worker() for _ in range(10)))
    assert peak <= 2
    assert pool.max_total_concurrency == 2


@pytest.mark.asyncio
async def test_key_pool_rotates_across_keys():
    pool = KeyPool([
        LLMAPIKeyCfg(key="k1", max_concurrency=4),
        LLMAPIKeyCfg(key="k2", max_concurrency=4),
    ])
    seen: list[str] = []

    async def grab():
        async with pool.acquire() as key:
            seen.append(key)

    await asyncio.gather(*(grab() for _ in range(6)))
    assert set(seen) == {"k1", "k2"}


@pytest.mark.asyncio
async def test_registry_rejects_duplicate_active_run():
    registry = SampleTaskRegistry()
    key = sample_identity_key(120, ["stock"], None, None)

    started = asyncio.Event()

    async def long_task():
        started.set()
        await asyncio.sleep(0.1)

    ok1, existing1 = await registry.try_register(key, "run-A", None, long_task)
    assert ok1 is True and existing1 is None
    assert registry.is_active(key)

    # Second submission with the same identity while A is running is rejected.
    ok2, existing2 = await registry.try_register(key, "run-B", None, long_task)
    assert ok2 is False and existing2 == "run-A"

    await started.wait()
    # Let the first task finish; the slot should free.
    await asyncio.sleep(0.2)
    assert not registry.is_active(key)

    ok3, existing3 = await registry.try_register(key, "run-C", None, long_task)
    assert ok3 is True and existing3 is None
    await asyncio.sleep(0.2)

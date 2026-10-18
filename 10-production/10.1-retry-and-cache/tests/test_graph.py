"""Offline tests for the shipping-quote graph: retries and caching."""

import asyncio

import pytest
from l10_1_retry_and_cache.graph import build_graph
from l10_1_retry_and_cache.service import (
    ParcelTooHeavy,
    RateServiceUnavailable,
    ShippingApi,
)
from langgraph.cache.memory import InMemoryCache


def test_retry_recovers_from_transient_failures() -> None:
    """Two outages, then success on the third attempt."""
    api = ShippingApi(rate_failures=2)
    graph = build_graph(api)
    result = asyncio.run(graph.ainvoke({"address": "Baker Street, London", "weight_kg": 2.0}))
    assert result["price"] == 8.0
    assert result["attempts"] == 3
    assert api.rate_calls == 3


def test_retries_stop_at_max_attempts() -> None:
    """A long outage surfaces the error after exactly max_attempts calls."""
    api = ShippingApi(rate_failures=10)
    graph = build_graph(api)
    with pytest.raises(RateServiceUnavailable):
        asyncio.run(graph.ainvoke({"address": "Baker Street, London", "weight_kg": 2.0}))
    assert api.rate_calls == 4


def test_errors_outside_retry_on_are_not_retried() -> None:
    """ParcelTooHeavy is not in retry_on, so there is exactly one call."""
    api = ShippingApi()
    graph = build_graph(api)
    with pytest.raises(ParcelTooHeavy):
        asyncio.run(graph.ainvoke({"address": "1 Rue de Rivoli, Paris", "weight_kg": 40.0}))
    assert api.rate_calls == 1


def test_cache_hit_for_same_address_in_other_spelling() -> None:
    """The key function normalises the address and ignores the weight."""
    api = ShippingApi()
    graph = build_graph(api, cache=InMemoryCache())
    asyncio.run(graph.ainvoke({"address": "12 Baker Street, London", "weight_kg": 2.0}))

    async def collect() -> list[dict]:
        return [
            chunk
            async for chunk in graph.astream(
                {"address": "  12 baker street, LONDON ", "weight_kg": 5.0},
                stream_mode="updates",
            )
        ]

    chunks = asyncio.run(collect())
    assert api.zone_lookups == 1
    zone_chunk = next(chunk for chunk in chunks if "lookup_zone" in chunk)
    assert zone_chunk["__metadata__"] == {"cached": True}


def test_cache_policy_without_backend_does_nothing() -> None:
    """Without a cache passed to compile(), every run does the lookup."""
    api = ShippingApi()
    graph = build_graph(api)
    request = {"address": "12 Baker Street, London", "weight_kg": 2.0}
    asyncio.run(graph.ainvoke(request))
    asyncio.run(graph.ainvoke(request))
    assert api.zone_lookups == 2

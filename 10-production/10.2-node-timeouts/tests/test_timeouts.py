"""Offline tests for the node timeouts on fetch_rate."""

import asyncio

import pytest
from l10_2_node_timeouts.graph import build_graph, retry_rate
from l10_2_node_timeouts.service import (
    ParcelTooHeavy,
    RateServiceUnavailable,
    ShippingApi,
)
from langgraph.errors import NodeTimeoutError


def test_idle_timeout_cuts_off_a_hang_and_retry_recovers() -> None:
    """One hung call is cancelled by the idle timeout; the retry answers."""
    api = ShippingApi(rate_hangs=1)
    graph = build_graph(api)
    result = asyncio.run(graph.ainvoke({"address": "12 Baker Street, London", "weight_kg": 2.0}))
    assert result["price"] == 8.0
    assert result["attempts"] == 2
    assert api.rate_calls == 2


def test_heartbeats_keep_a_slow_call_alive() -> None:
    """0.2 s of work (twice idle_timeout) succeeds because it heartbeats."""
    api = ShippingApi(rate_steps=8)
    graph = build_graph(api)
    result = asyncio.run(graph.ainvoke({"address": "12 Baker Street, London", "weight_kg": 2.0}))
    assert result["price"] == 8.0
    assert result["attempts"] == 1
    assert api.rate_calls == 1


def test_permanent_hang_exhausts_retries() -> None:
    """Every attempt hits the idle timeout, so all max_attempts are used."""
    api = ShippingApi(rate_hangs=10)
    graph = build_graph(api)
    with pytest.raises(NodeTimeoutError) as exc:
        asyncio.run(graph.ainvoke({"address": "1 Rue de Rivoli, Paris", "weight_kg": 1.0}))
    assert exc.value.kind == "idle"
    assert exc.value.timeout == 0.1
    assert exc.value.node == "fetch_rate"
    assert api.rate_calls == 4


def test_run_timeout_is_a_hard_cap_and_not_retried() -> None:
    """Heartbeats don't extend the run timeout, and retry_rate skips it."""
    api = ShippingApi(rate_steps=40)
    graph = build_graph(api)
    with pytest.raises(NodeTimeoutError) as exc:
        asyncio.run(graph.ainvoke({"address": "10 Unter den Linden, Berlin", "weight_kg": 1.0}))
    assert exc.value.kind == "run"
    assert exc.value.timeout == 0.3
    assert api.rate_calls == 1


def test_retry_rate_decisions() -> None:
    """retry_rate retries outages and idle timeouts only."""
    assert retry_rate(RateServiceUnavailable("x"))
    assert retry_rate(NodeTimeoutError("fetch_rate", 0.1, kind="idle", idle_timeout=0.1))
    assert not retry_rate(NodeTimeoutError("fetch_rate", 0.3, kind="run", run_timeout=0.3))
    assert not retry_rate(ParcelTooHeavy("x"))
    # The reason the default retry_on retries timeouts at all.
    assert not issubclass(NodeTimeoutError, TimeoutError)

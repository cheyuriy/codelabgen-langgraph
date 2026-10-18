"""Offline tests for the error handlers and the node defaults."""

import asyncio

from l10_3_error_handlers.graph import RATE_RETRY, RATE_TIMEOUT, ZONE_CACHE, build_graph
from l10_3_error_handlers.service import ShippingApi


def test_healthy_quote_gets_a_reply() -> None:
    """Without trouble, write_reply answers and no handler runs."""
    api = ShippingApi()
    graph = build_graph(api)
    result = asyncio.run(graph.ainvoke({"address": "12 Baker Street, London", "weight_kg": 2.0}))
    assert result["reply"] == "8.0 EUR to UK"
    assert "error" not in result


def test_outage_ends_in_an_estimate_from_the_node_handler() -> None:
    """After the retries run out, fallback_quote writes a flat-rate estimate."""
    api = ShippingApi(rate_failures=10)
    graph = build_graph(api)
    result = asyncio.run(graph.ainvoke({"address": "12 Baker Street, London", "weight_kg": 2.0}))
    assert result["price"] == 18.0
    assert result["error"] == "RateServiceUnavailable in fetch_rate"
    assert result["reply"] == "estimated 18.0 EUR to UK (RateServiceUnavailable in fetch_rate)"
    # fetch_rate never succeeded, so it never wrote `attempts`.
    assert "attempts" not in result
    assert api.rate_calls == 4


def test_unknown_city_is_caught_by_the_default_handler() -> None:
    """record_failure catches lookup_zone's KeyError and skips fetch_rate."""
    api = ShippingApi()
    graph = build_graph(api)
    result = asyncio.run(graph.ainvoke({"address": "1 Via Roma, Rome", "weight_kg": 1.0}))
    assert result["reply"] == "no quote (KeyError in lookup_zone)"
    assert "zone" not in result
    assert "price" not in result
    assert api.rate_calls == 0  # fetch_rate was skipped
    assert api.zone_lookups == 1  # the KeyError was not retried


def test_node_defaults_on_the_compiled_graph() -> None:
    """Retry and timeout reach every node, handlers included; caching does not."""
    graph = build_graph(ShippingApi())
    for name in (
        "lookup_zone",
        "fetch_rate",
        "write_reply",
        "__error_handler__fetch_rate",
        "__default_error_handler__",
    ):
        # The compiled PregelNode stores the retry policies as a tuple.
        assert graph.nodes[name].retry_policy == (RATE_RETRY,)
        assert graph.nodes[name].timeout == RATE_TIMEOUT
    assert graph.nodes["lookup_zone"].cache_policy == ZONE_CACHE
    assert graph.nodes["__error_handler__fetch_rate"].cache_policy is None
    assert graph.nodes["__default_error_handler__"].cache_policy is None

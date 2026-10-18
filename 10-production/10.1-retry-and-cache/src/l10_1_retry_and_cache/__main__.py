"""Live run: four shipping quotes that show retries and caching at work."""

import asyncio
from typing import Any

from langgraph.cache.memory import InMemoryCache

from l10_1_retry_and_cache.graph import build_graph
from l10_1_retry_and_cache.service import (
    ParcelTooHeavy,
    RateServiceUnavailable,
    ShippingApi,
)


# region main
async def show_quote(graph: Any, request: dict[str, Any]) -> None:
    """Run one quote and print every node update as it arrives."""
    # "updates" yields one dict per finished node. A node answered from the
    # cache also carries {'__metadata__': {'cached': True}}.
    async for update in graph.astream(request, stream_mode="updates"):
        print(update)


async def main() -> None:
    """Run the four sections against one API and one shared cache."""
    # The rate service will fail the next 2 calls, then recover.
    api = ShippingApi(rate_failures=2)
    # One graph and one InMemoryCache for all quotes, so the cache survives
    # between them. fetch_rate is async, so the graph is run with
    # astream/ainvoke; a sync invoke() raises TypeError.
    graph = build_graph(api, cache=InMemoryCache())

    print("== 1. The rate service fails twice, the retry policy recovers ==")
    await show_quote(graph, {"address": "12 Baker Street, London", "weight_kg": 2.0})
    print(f"rate service calls: {api.rate_calls}")

    print()
    print("== 2. Same address, other spelling: the zone comes from the cache ==")
    await show_quote(graph, {"address": "  12 baker street, LONDON ", "weight_kg": 5.0})
    print(f"zone lookups: {api.zone_lookups}")

    print()
    print("== 3. The service stays down: retries run out ==")
    api.rate_failures = 10
    calls_before = api.rate_calls
    try:
        await graph.ainvoke({"address": "1 Rue de Rivoli, Paris", "weight_kg": 1.0})
    except RateServiceUnavailable as error:
        # After the last attempt LangGraph re-raises the node's own error.
        print(f"gave up after {api.rate_calls - calls_before} calls: {error}")

    print()
    print("== 4. A bad request is not retried ==")
    api.rate_failures = 0
    calls_before = api.rate_calls
    try:
        await graph.ainvoke({"address": "1 Rue de Rivoli, Paris", "weight_kg": 40.0})
    except ParcelTooHeavy as error:
        # ParcelTooHeavy is not in retry_on, so the first failure is final.
        calls = api.rate_calls - calls_before
        print(f"failed after {calls} call{'s' if calls != 1 else ''}: {error}")

    # The Paris zone from section 3 was cached although that run failed:
    # only the failing node's result is left out of the cache.
    print(f"zone lookups in total: {api.zone_lookups}")


if __name__ == "__main__":
    asyncio.run(main())
# endregion

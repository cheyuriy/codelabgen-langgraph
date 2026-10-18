"""Live run: five shipping quotes that show error handlers and node defaults at work."""

import asyncio
from typing import Any

from langgraph.cache.memory import InMemoryCache

from l10_3_error_handlers.graph import build_graph
from l10_3_error_handlers.service import ParcelTooHeavy, ShippingApi


# region main
async def show_quote(graph: Any, request: dict[str, Any]) -> None:
    """Run one quote and print every node update as it arrives."""
    # "updates" yields one dict per finished node. A node answered from the
    # cache also carries {'__metadata__': {'cached': True}}. Error-handler
    # nodes show up under their own names, such as
    # "__error_handler__fetch_rate".
    async for update in graph.astream(request, stream_mode="updates"):
        print(update)


async def main() -> None:
    """Run the five sections against one API and one shared cache."""
    # The rate service starts healthy; each section scripts its own trouble.
    api = ShippingApi()
    # One graph and one InMemoryCache for all quotes, so the cache survives
    # between them. Every node is async and has a timeout, so the graph is
    # run with astream/ainvoke. A sync invoke() raises TypeError: No
    # synchronous function provided to "__default_error_handler__" (the
    # async lookup_zone fails, then the async default handler does too).
    graph = build_graph(api, cache=InMemoryCache())

    print("== 1. A healthy quote: lookup_zone -> fetch_rate -> write_reply ==")
    await show_quote(graph, {"address": "12 Baker Street, London", "weight_kg": 2.0})

    print()
    print(
        "== 2. The rate service is down: retries run out, "
        "then fetch_rate's handler sends an estimate =="
    )
    api.rate_failures = 10
    calls_before = api.rate_calls
    # All 4 attempts of RATE_RETRY run first, and the handler sees only the
    # last error.
    await show_quote(graph, {"address": "5 Market Street, Manchester", "weight_kg": 3.0})
    print(f"rate service calls: {api.rate_calls - calls_before}")

    print()
    print("== 3. The service hangs for good: every attempt times out, then the same handler ==")
    # 6 scripted failures are left over from section 2; clear them.
    api.rate_failures = 0
    api.rate_hangs = 10
    calls_before = api.rate_calls
    # Timeout, then retry, four times over, then the handler: about 0.75 s.
    await show_quote(graph, {"address": "1 Rue de Rivoli, Paris", "weight_kg": 1.0})
    print(f"rate service calls: {api.rate_calls - calls_before}")

    print()
    print(
        "== 4. An unknown city: the default handler from set_node_defaults catches lookup_zone =="
    )
    api.rate_hangs = 0
    calls_before = api.rate_calls
    # lookup_zone raises KeyError, retry_rate does not retry it, and
    # record_failure routes straight to write_reply: fetch_rate never runs.
    await show_quote(graph, {"address": "1 Via Roma, Rome", "weight_kg": 1.0})
    print(f"rate service calls: {api.rate_calls - calls_before}")

    print()
    print("== 5. A parcel that is too heavy: the handler re-raises what it cannot fix ==")
    calls_before = api.rate_calls
    try:
        await show_quote(graph, {"address": "10 Unter den Linden, Berlin", "weight_kg": 40.0})
    except ParcelTooHeavy as error:
        # fallback_quote re-raised ParcelTooHeavy. An exception raised in a
        # handler fails the run, and it reaches the caller unchanged.
        print(f"run failed: {error}")
    print(f"rate service calls: {api.rate_calls - calls_before}")


if __name__ == "__main__":
    asyncio.run(main())
# endregion

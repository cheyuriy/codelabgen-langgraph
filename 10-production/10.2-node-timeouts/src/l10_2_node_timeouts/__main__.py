"""Live run: four shipping quotes that show node timeouts at work."""

import asyncio
import time
from typing import Any

from langgraph.cache.memory import InMemoryCache
from langgraph.errors import NodeTimeoutError

from l10_2_node_timeouts.graph import RATE_TIMEOUT, build_graph
from l10_2_node_timeouts.service import ShippingApi


# region main
async def show_quote(graph: Any, request: dict[str, Any]) -> None:
    """Run one quote and print every node update as it arrives."""
    # "updates" yields one dict per finished node. A node answered from the
    # cache also carries {'__metadata__': {'cached': True}}.
    async for update in graph.astream(request, stream_mode="updates"):
        print(update)


async def main() -> None:
    """Run the four sections against one API and one shared cache."""
    # The rate service starts healthy; each section scripts its own trouble.
    api = ShippingApi()
    # One graph and one InMemoryCache for all quotes, so the cache survives
    # between them. fetch_rate is async and has a timeout, so the graph is
    # run with astream/ainvoke. A sync invoke() raises ValueError ("Node
    # timeouts are only supported for async nodes ... Node 'fetch_rate' is
    # sync.").
    graph = build_graph(api, cache=InMemoryCache())

    print("== 1. The rate service hangs once: the idle timeout cuts it off, a retry recovers ==")
    # The first call hangs. After 0.1 s without a heartbeat LangGraph cancels
    # it, retry_rate says "idle, retry", and the second call answers at once.
    api.rate_hangs = 1
    await show_quote(graph, {"address": "12 Baker Street, London", "weight_kg": 2.0})
    print(f"rate service calls: {api.rate_calls}")

    print()
    print("== 2. A slow quote that reports progress: heartbeats keep it alive ==")
    # 8 steps of 0.025 s: 0.2 s of work, twice the idle timeout. Each step
    # calls runtime.heartbeat, so the idle clock never runs out.
    api.rate_steps = 8
    start = time.monotonic()
    await show_quote(graph, {"address": "5 Market Street, Manchester", "weight_kg": 3.0})
    elapsed = time.monotonic() - start
    # A comparison, not a rounded time, so the output does not depend on
    # how busy the machine is.
    print(
        f"took longer than idle_timeout={RATE_TIMEOUT.idle_timeout} s: "
        f"{elapsed > RATE_TIMEOUT.idle_timeout}"
    )

    print()
    print("== 3. The service hangs for good: every attempt times out ==")
    api.rate_steps = 0
    api.rate_hangs = 10
    calls_before = api.rate_calls
    try:
        await graph.ainvoke({"address": "1 Rue de Rivoli, Paris", "weight_kg": 1.0})
    except NodeTimeoutError as error:
        # 4 attempts x 0.1 s plus 0.05 + 0.1 + 0.2 s of backoff, about 0.75 s.
        # After the last attempt the NodeTimeoutError itself reaches the
        # caller. Its fields say which limit fired, where, and how big it was.
        # (str(error) also contains the measured elapsed time, which varies
        # from run to run, so it is not printed here.)
        calls = api.rate_calls - calls_before
        print(
            f"gave up after {calls} call{'s' if calls != 1 else ''}: "
            f"{error.kind} timeout of {error.timeout} s in {error.node}"
        )

    print()
    print("== 4. Progress without end: the run timeout is the hard cap ==")
    # 6 scripted hangs are left over from section 3; clear them.
    api.rate_hangs = 0
    # 40 steps: 1 s of work, heart-beating all the way.
    api.rate_steps = 40
    calls_before = api.rate_calls
    try:
        await graph.ainvoke({"address": "10 Unter den Linden, Berlin", "weight_kg": 1.0})
    except NodeTimeoutError as error:
        # Heartbeats kept the idle clock fresh, but the run timeout cut the
        # attempt off anyway after 0.3 s, and retry_rate does not retry a
        # run timeout.
        calls = api.rate_calls - calls_before
        print(
            f"gave up after {calls} call{'s' if calls != 1 else ''}: "
            f"{error.kind} timeout of {error.timeout} s in {error.node}"
        )


if __name__ == "__main__":
    asyncio.run(main())
# endregion

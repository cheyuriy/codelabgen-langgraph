"""The shipping-quote graph: a cached zone lookup and a retried, timed rate call.

START -> lookup_zone -> fetch_rate -> END
"""

from typing import TypedDict

from langgraph.cache.base import BaseCache
from langgraph.errors import NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import CachePolicy, RetryPolicy, TimeoutPolicy

from l10_2_node_timeouts.service import RateServiceUnavailable, ShippingApi


# region state
class QuoteState(TypedDict):
    """The quote request and the answer the graph builds up."""

    address: str
    weight_kg: float
    zone: str  # written by lookup_zone
    price: float  # written by fetch_rate
    attempts: int  # written by fetch_rate: the attempt that succeeded


# endregion


# region retry_policy
def retry_rate(error: Exception) -> bool:
    """Decide whether fetch_rate is retried after `error`.

    A call that went silent (an idle timeout) is probably a dropped
    connection, so a fresh attempt can succeed. A call that kept working
    until the hard cap (a run timeout) would most likely hit the cap again,
    so retrying it only multiplies the wait. ParcelTooHeavy is still never
    retried.
    """
    if isinstance(error, NodeTimeoutError):
        # NodeTimeoutError is not a subclass of the built-in TimeoutError,
        # which is why the default retry_on (default_retry_on) does retry it.
        # `kind` says which limit fired: "idle" or "run".
        return error.kind == "idle"
    return isinstance(error, RateServiceUnavailable)


# How LangGraph retries fetch_rate when it raises.
RATE_RETRY = RetryPolicy(
    # max_attempts counts the first try: 1 call + up to 3 retries.
    max_attempts=4,
    # Waits between attempts: 0.05, 0.1, 0.2 s (each one x backoff_factor).
    # Real services use seconds here.
    initial_interval=0.05,
    backoff_factor=2.0,
    # In production keep jitter=True: in 1.2.16 it adds a random 0-1 s to
    # every wait, so many clients don't retry in lockstep. It is off here
    # only to keep the demo fast and repeatable.
    jitter=False,
    # Retry the transient errors only: ParcelTooHeavy fails at once.
    # retry_on can also be a function that gets the exception.
    retry_on=retry_rate,
)
# endregion

# region timeout_policy
# How long one attempt of fetch_rate may take. Both limits apply to a single
# attempt, and each retry starts with fresh clocks.
RATE_TIMEOUT = TimeoutPolicy(
    # Hard wall-clock cap in seconds. Heartbeats never extend it.
    run_timeout=0.3,
    # Fires when the attempt shows no progress for this many seconds. In this
    # node the only progress signal is runtime.heartbeat(). With the default
    # refresh_on="auto", node writes, stream chunks, child tasks and
    # LangChain callbacks also count; refresh_on="heartbeat" counts
    # heartbeats only.
    idle_timeout=0.1,
)
# A plain number, `timeout=0.3`, means run_timeout only. Real services use
# seconds to minutes; the values are tiny only to keep the demo fast.
# endregion


# region cache_policy
def zone_cache_key(state: QuoteState) -> str:
    """Build the cache key for lookup_zone from the node's input.

    The key function receives the node's whole input. The zone depends only
    on the address, so the key ignores the weight and normalises spelling.
    (The default key pickles the entire input, weight included.)
    """
    return state["address"].strip().lower()


# Cache lookup_zone results for 10 minutes; ttl is in seconds, None = forever.
ZONE_CACHE = CachePolicy(key_func=zone_cache_key, ttl=600)
# endregion


# region build_graph
def build_graph(api: ShippingApi, cache: BaseCache | None = None):
    """Build and compile the quote graph around a ShippingApi.

    `cache` is the backend that stores cached node results, for example an
    InMemoryCache. Without it the CachePolicy has no effect.
    """

    # region nodes
    def lookup_zone(state: QuoteState) -> dict[str, str]:
        """Find the shipping zone for the address (the expensive, cached step)."""
        return {"zone": api.lookup_zone(state["address"])}

    async def fetch_rate(state: QuoteState, runtime: Runtime) -> dict[str, float | int]:
        """Ask the flaky rate service for the price (the retried step)."""
        # runtime.heartbeat records progress for the idle timeout. It is a
        # no-op when the node has no idle timeout.
        price = await api.get_rate(state["zone"], state["weight_kg"], on_progress=runtime.heartbeat)
        # LangGraph injects `runtime` because of the parameter's name and
        # annotation. node_attempt is 1 on the first try and counts up on
        # every retry.
        return {"price": price, "attempts": runtime.execution_info.node_attempt}

    # endregion

    builder = StateGraph(QuoteState)
    # The policies are attached per node, when the node is added.
    builder.add_node("lookup_zone", lookup_zone, cache_policy=ZONE_CACHE)
    # Timeouts work only on async nodes. Putting one on the sync lookup_zone
    # is accepted by add_node but makes compile() raise ValueError.
    builder.add_node("fetch_rate", fetch_rate, retry_policy=RATE_RETRY, timeout=RATE_TIMEOUT)
    builder.add_edge(START, "lookup_zone")
    builder.add_edge("lookup_zone", "fetch_rate")
    builder.add_edge("fetch_rate", END)
    # A CachePolicy only declares what to cache. Without a cache backend
    # passed to compile(), nothing is cached and no error is raised.
    return builder.compile(cache=cache)


# endregion

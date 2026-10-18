"""The shipping-quote graph: a cached zone lookup and a retried rate call.

START -> lookup_zone -> fetch_rate -> END
"""

from typing import TypedDict

from langgraph.cache.base import BaseCache
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import CachePolicy, RetryPolicy

from l10_1_retry_and_cache.service import RateServiceUnavailable, ShippingApi


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
    # Retry the transient error only: ParcelTooHeavy fails at once.
    retry_on=RateServiceUnavailable,
)
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
        price = await api.get_rate(state["zone"], state["weight_kg"])
        # LangGraph injects `runtime` because of the parameter's name and
        # annotation. node_attempt is 1 on the first try and counts up on
        # every retry.
        return {"price": price, "attempts": runtime.execution_info.node_attempt}

    # endregion

    builder = StateGraph(QuoteState)
    # The policies are attached per node, when the node is added.
    builder.add_node("lookup_zone", lookup_zone, cache_policy=ZONE_CACHE)
    builder.add_node("fetch_rate", fetch_rate, retry_policy=RATE_RETRY)
    builder.add_edge(START, "lookup_zone")
    builder.add_edge("lookup_zone", "fetch_rate")
    builder.add_edge("fetch_rate", END)
    # A CachePolicy only declares what to cache. Without a cache backend
    # passed to compile(), nothing is cached and no error is raised.
    return builder.compile(cache=cache)


# endregion

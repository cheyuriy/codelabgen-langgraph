"""The shipping-quote graph: shared node defaults, a fallback quote when the
rate call fails, and a reply.

START -> lookup_zone -> fetch_rate -> write_reply -> END
On failure: fetch_rate -> __error_handler__fetch_rate,
any other node -> __default_error_handler__; both go to write_reply
"""

from typing import Literal, TypedDict

from langgraph.cache.base import BaseCache
from langgraph.errors import NodeError, NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import CachePolicy, Command, RetryPolicy, TimeoutPolicy

from l10_3_error_handlers.service import RateServiceUnavailable, ShippingApi


# region state
class QuoteState(TypedDict):
    """The quote request and the answer the graph builds up."""

    address: str
    weight_kg: float
    zone: str  # written by lookup_zone
    price: float  # written by fetch_rate
    attempts: int  # written by fetch_rate: the attempt that succeeded
    error: str  # written by an error handler: which error, in which node
    reply: str  # written by write_reply
    # Keys that no node has written are absent from the state a node
    # receives (not None), so write_reply checks them with `in`.


# endregion


# region retry_policy
def retry_rate(error: Exception) -> bool:
    """Decide whether a node is retried after `error`.

    A call that went silent (an idle timeout) is probably a dropped
    connection, so a fresh attempt can succeed. A call that kept working
    until the hard cap (a run timeout) would most likely hit the cap again,
    so retrying it only multiplies the wait. ParcelTooHeavy and any other
    error (such as lookup_zone's KeyError) are never retried.
    """
    if isinstance(error, NodeTimeoutError):
        # NodeTimeoutError is not a subclass of the built-in TimeoutError,
        # which is why the default retry_on (default_retry_on) does retry it.
        # `kind` says which limit fired: "idle" or "run".
        return error.kind == "idle"
    return isinstance(error, RateServiceUnavailable)


# Now a graph-wide default (see build_graph): it also covers lookup_zone,
# write_reply and the handler nodes. retry_rate returns False for
# lookup_zone's KeyError, so an unknown city is not retried.
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
# Now a graph-wide default (see build_graph): it also covers lookup_zone,
# write_reply and the handler nodes.
# Both limits apply to a single attempt, and each retry starts with fresh
# clocks.
RATE_TIMEOUT = TimeoutPolicy(
    # Hard wall-clock cap in seconds. Heartbeats never extend it.
    run_timeout=0.3,
    # Fires when the attempt shows no progress for this many seconds. In
    # fetch_rate the only progress signal is runtime.heartbeat(). With the
    # default refresh_on="auto", node writes, stream chunks, child tasks and
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


# region error_handlers
# A flat rate above every zone's real rate (UK 4.0, EU 7.5), so an estimate
# never undercharges.
FALLBACK_RATE_PER_KG = 9.0


def describe_failure(error: NodeError) -> str:
    """Say which error happened in which node, e.g. "KeyError in lookup_zone".

    Only the exception's type name is used, never str(error.error): a
    NodeTimeoutError's message contains the measured elapsed time and would
    make the output vary between runs.
    """
    return f"{type(error.error).__name__} in {error.node}"


# Both handlers are async because the default timeout also applies to
# handler nodes, and a timed node must be async.
async def fallback_quote(state: QuoteState, error: NodeError) -> Command[Literal["write_reply"]]:
    """fetch_rate's own error handler: reply with a flat-rate estimate.

    It runs once, after RATE_RETRY has used up its attempts (each one bounded
    by RATE_TIMEOUT), or right after the first error that is not retried. It
    receives fetch_rate's input state and the final exception. LangGraph
    injects `error` because of the NodeError annotation.
    """
    if not isinstance(error.error, (RateServiceUnavailable, NodeTimeoutError)):
        # A request error such as ParcelTooHeavy cannot be fixed by an
        # estimate, so re-raise it. An exception raised in a handler fails
        # the run: no other handler catches it.
        raise error.error
    # goto is needed: fetch_rate's own edge to write_reply does not fire
    # when fetch_rate failed, so a plain dict would end the run here.
    # LangGraph does not read a handler's return annotation (and draws no
    # edge from a handler node): the Literal only names goto for the reader.
    return Command(
        update={
            "price": FALLBACK_RATE_PER_KG * state["weight_kg"],
            "error": describe_failure(error),
        },
        goto="write_reply",
    )


async def record_failure(state: QuoteState, error: NodeError) -> Command[Literal["write_reply"]]:
    """The graph-wide default handler for any regular node without its own.

    In this graph that means lookup_zone and write_reply. It records what
    went wrong and routes to write_reply, skipping the nodes in between.
    """
    return Command(update={"error": describe_failure(error)}, goto="write_reply")


# endregion


# region build_graph
def build_graph(api: ShippingApi, cache: BaseCache | None = None):
    """Build and compile the quote graph around a ShippingApi.

    Every node gets the shared retry policy, timeout and default error
    handler (record_failure); fetch_rate has its own handler, fallback_quote.
    `cache` is the backend that stores cached node results, for example an
    InMemoryCache. Without it the CachePolicy has no effect.
    """

    # region nodes
    # async only because the default timeout now covers every node, and
    # compile() rejects a timed sync node. The ShippingApi method stays sync.
    async def lookup_zone(state: QuoteState) -> dict[str, str]:
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

    async def write_reply(state: QuoteState) -> dict[str, str]:
        """Turn the quote into the reply for the customer."""
        if "price" not in state:
            return {"reply": f"no quote ({state['error']})"}
        elif "error" in state:
            return {
                "reply": f"estimated {state['price']} EUR to {state['zone']} ({state['error']})"
            }
        else:
            return {"reply": f"{state['price']} EUR to {state['zone']}"}

    # endregion

    # region node_defaults
    builder = StateGraph(QuoteState)
    # These apply to every node that does not set its own value in add_node,
    # and they are applied at compile() time, whatever the order of calls.
    # retry and timeout also cover the error-handler nodes; error_handler
    # and cache_policy cover regular nodes only. The defaults are not
    # inherited by subgraphs.
    builder.set_node_defaults(
        retry_policy=RATE_RETRY,
        timeout=RATE_TIMEOUT,
        error_handler=record_failure,
    )
    builder.add_node("lookup_zone", lookup_zone, cache_policy=ZONE_CACHE)
    # A per-node handler wins over the default one. LangGraph adds it as the
    # node "__error_handler__fetch_rate". retry and timeout now come from
    # the defaults.
    builder.add_node("fetch_rate", fetch_rate, error_handler=fallback_quote)
    builder.add_node("write_reply", write_reply)
    # endregion
    builder.add_edge(START, "lookup_zone")
    builder.add_edge("lookup_zone", "fetch_rate")
    builder.add_edge("fetch_rate", "write_reply")
    builder.add_edge("write_reply", END)
    # A CachePolicy only declares what to cache. Without a cache backend
    # passed to compile(), nothing is cached and no error is raised.
    return builder.compile(cache=cache)


# endregion

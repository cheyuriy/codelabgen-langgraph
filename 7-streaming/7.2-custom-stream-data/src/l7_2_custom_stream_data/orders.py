"""An order goes through pick, pack and ship: the graph the whole module streams.

The graph is deliberately tiny and linear, so the stream output is easy to
read. Every lesson in module 7 streams this same order through it.
"""

from typing import NotRequired, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime


# region order_state
class OrderState(TypedDict):
    """The state of one order.

    The input holds only `order_id` and `items`; the nodes fill in the rest,
    which is why those keys are `NotRequired`.
    """

    order_id: str
    items: list[str]  # SKUs, e.g. ["PEN", "NOTEBOOK"]
    status: NotRequired[str]
    box: NotRequired[str]
    tracking: NotRequired[str]


# endregion


# region nodes
# Each node returns ONLY the keys it changes, not the whole state. LangGraph
# merges that partial dict into the state. This is exactly what makes the two
# stream modes differ: "updates" shows these partial dicts as they are,
# "values" shows the full state after they were merged.
def pick(state: OrderState) -> dict:
    """Pick the items from the shelves."""
    return {"status": "picked"}


def pack(state: OrderState) -> dict:
    """Pack the items one by one, reporting progress after each item."""
    # get_stream_writer() returns the writer of the CURRENT run: it reads it
    # from the run's context, so call it inside the node while the run
    # executes it, never at import time (outside a run it raises RuntimeError).
    writer = get_stream_writer()
    total = len(state["items"])
    for done, sku in enumerate(state["items"], start=1):
        # The writer is a plain callable: writer(data). data can be any value;
        # a dict is the convention. It goes to the stream at once, not when the
        # node returns, and it does NOT go into the state.
        # Build a fresh dict for every call: the writer does not copy what you
        # pass, so reusing and mutating one dict would change what the caller sees.
        writer({"node": "pack", "item": sku, "done": done, "total": total})
    return {"status": "packed", "box": "small" if total <= 2 else "large"}


def ship(state: OrderState, runtime: Runtime) -> dict:
    """Hand the parcel to the carrier, report the label, record tracking."""
    # The second way to get the same writer: LangGraph sees the
    # `runtime: Runtime` parameter and injects the run's Runtime (lesson 2.4).
    # Its stream_writer field is the writer get_stream_writer() would return.
    # Because it arrives as an argument, ship can be called in a test with a
    # hand-made Runtime (section d of __main__.py).
    tracking = f"TRK-{state['order_id']}"
    runtime.stream_writer({"node": "ship", "label": tracking})
    return {"status": "shipped", "tracking": tracking}


# endregion


# region build_graph
def build_graph() -> CompiledStateGraph:
    """Build the linear order graph: START -> pick -> pack -> ship -> END."""
    builder = StateGraph(OrderState)
    builder.add_node("pick", pick)
    builder.add_node("pack", pack)
    builder.add_node("ship", ship)
    # Each node runs in its own super-step, so every step yields one chunk per mode.
    builder.add_edge(START, "pick")
    builder.add_edge("pick", "pack")
    builder.add_edge("pack", "ship")
    builder.add_edge("ship", END)
    return builder.compile()


# endregion

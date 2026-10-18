"""An order goes through pick, pack and ship: the graph the whole module streams.

The graph is deliberately tiny and linear, so the stream output is easy to
read. Every lesson in module 7 streams this same order through it.
"""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


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
    """Pack the items; two items or fewer fit in a small box."""
    return {"status": "packed", "box": "small" if len(state["items"]) <= 2 else "large"}


def ship(state: OrderState) -> dict:
    """Hand the parcel to the carrier and record its tracking number."""
    return {"status": "shipped", "tracking": f"TRK-{state['order_id']}"}


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

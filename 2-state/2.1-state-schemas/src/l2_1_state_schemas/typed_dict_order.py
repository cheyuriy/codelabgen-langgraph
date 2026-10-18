"""The order pipeline with a TypedDict state schema.

START -> compute_subtotal -> apply_tax -> END

A TypedDict is only a type hint: at run time the state is a plain dict.
There are no defaults and no validation, so the caller must pass every key
the nodes read (including tax_rate and currency).
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


# region typed_dict_state
class OrderDict(TypedDict):
    """Order state as a TypedDict: seven keys, no defaults, no checks.

    LangGraph turns each key into a channel. Nothing stops a caller from
    leaving a key out or passing a wrong type.
    """

    customer: str
    quantity: int
    unit_price: float
    tax_rate: float  # e.g. 0.2 for 20% VAT; the caller must pass it
    currency: str  # e.g. "EUR"; the caller must pass it
    subtotal: float  # written by compute_subtotal
    total: float  # written by apply_tax


# endregion


# region typed_dict_nodes
def compute_subtotal(state: OrderDict) -> dict[str, float]:
    """Multiply quantity by unit_price into subtotal."""
    # The node receives a plain dict, so it uses key access.
    return {"subtotal": state["quantity"] * state["unit_price"]}


def apply_tax(state: OrderDict) -> dict[str, float]:
    """Add tax to subtotal and round the result into total."""
    # A missing "tax_rate" raises KeyError right here: no defaults exist.
    return {"total": round(state["subtotal"] * (1 + state["tax_rate"]), 2)}


# endregion


# region typed_dict_graph
def build_graph() -> CompiledStateGraph:
    """Wire the two nodes into a linear graph and compile it."""
    # The schema passed to StateGraph decides which keys (channels) exist.
    builder = StateGraph(OrderDict)
    builder.add_node("compute_subtotal", compute_subtotal)
    builder.add_node("apply_tax", apply_tax)
    builder.add_edge(START, "compute_subtotal")
    builder.add_edge("compute_subtotal", "apply_tax")
    builder.add_edge("apply_tax", END)
    return builder.compile()


# endregion

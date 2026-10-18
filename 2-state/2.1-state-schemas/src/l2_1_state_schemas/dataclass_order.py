"""The order pipeline with a dataclass state schema.

Same graph as typed_dict_order.py. Only the schema and the state access
change: a dataclass gives defaults, and nodes read attributes.
"""

from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


# region dataclass_state
@dataclass
class OrderData:
    """Order state as a dataclass, with defaults for the optional fields.

    Before each node runs, LangGraph builds an OrderData from the stored
    values, so missing keys get their defaults. Types are not checked.
    """

    customer: str
    quantity: int
    unit_price: float
    tax_rate: float = 0.2
    currency: str = "EUR"
    subtotal: float = 0.0
    total: float = 0.0


# endregion


# region dataclass_nodes
def compute_subtotal(state: OrderData) -> dict[str, float]:
    """Multiply quantity by unit_price into subtotal."""
    # The node receives an OrderData instance, so it uses attribute access.
    # It still returns a partial update as a dict.
    return {"subtotal": state.quantity * state.unit_price}


def apply_tax(state: OrderData) -> dict[str, float]:
    """Add tax to subtotal and round the result into total."""
    # tax_rate comes from the dataclass default when the caller left it out.
    return {"total": round(state.subtotal * (1 + state.tax_rate), 2)}


# endregion


def build_graph() -> CompiledStateGraph:
    """Wire the two nodes into a linear graph and compile it."""
    builder = StateGraph(OrderData)
    builder.add_node("compute_subtotal", compute_subtotal)
    builder.add_node("apply_tax", apply_tax)
    builder.add_edge(START, "compute_subtotal")
    builder.add_edge("compute_subtotal", "apply_tax")
    builder.add_edge("apply_tax", END)
    return builder.compile()

"""The order pipeline with a Pydantic state schema.

Same graph again. Pydantic adds validation: LangGraph calls
OrderModel(**state) when it builds each node's input, so bad input fails
before the first node runs. Node updates are not validated when written.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field


# region pydantic_state
class OrderModel(BaseModel):
    """Order state as a Pydantic model: defaults plus validation rules."""

    customer: str
    # Field(gt=0) rejects zero and negative values with a ValidationError.
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    tax_rate: float = 0.2
    currency: str = "EUR"
    subtotal: float = 0.0
    total: float = 0.0


# endregion


# region pydantic_nodes
def compute_subtotal(state: OrderModel) -> dict[str, float]:
    """Multiply quantity by unit_price into subtotal."""
    # state is a validated OrderModel: quantity is an int > 0 here, even if
    # the caller passed the string "3" (Pydantic's lax mode coerces it).
    return {"subtotal": state.quantity * state.unit_price}


def apply_tax(state: OrderModel) -> dict[str, float]:
    """Add tax to subtotal and round the result into total."""
    return {"total": round(state.subtotal * (1 + state.tax_rate), 2)}


# endregion


def build_graph() -> CompiledStateGraph:
    """Wire the two nodes into a linear graph and compile it."""
    builder = StateGraph(OrderModel)
    builder.add_node("compute_subtotal", compute_subtotal)
    builder.add_node("apply_tax", apply_tax)
    builder.add_edge(START, "compute_subtotal")
    builder.add_edge("compute_subtotal", "apply_tax")
    builder.add_edge("apply_tax", END)
    return builder.compile()

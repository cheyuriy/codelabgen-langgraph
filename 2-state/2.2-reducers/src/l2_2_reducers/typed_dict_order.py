"""The order pipeline with a cart, an audit log and reducers.

START -> check_stock -> apply_bundle -> compute_subtotal -> apply_tax -> END

Each state key has a rule for combining a node's update with the stored
value. Without a reducer the update replaces the value (last write wins);
an Annotated reducer combines the two instead.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite

STOCK = {"PEN": 10, "NOTEBOOK": 2, "MUG": 0}  # an unknown sku counts as 0
STARTER_KIT = {"PEN": 3, "NOTEBOOK": 1}  # the cart that becomes one kit line


class LineItem(TypedDict):
    """One cart line: a product, how many, and the price of one."""

    sku: str
    quantity: int
    unit_price: float


KIT_ITEM: LineItem = {"sku": "STARTER-KIT", "quantity": 1, "unit_price": 6.0}


# region merge_items_reducer
def merge_items(current: list[LineItem], update: list[LineItem]) -> list[LineItem]:
    """Upsert update into current by sku; quantity <= 0 removes the line.

    LangGraph calls this as merge_items(stored_value, node_update) for every
    write to "items", including the invoke input. It must return a new list:
    the stored value is never mutated.
    """
    # A dict keeps insertion order, so existing lines keep their position.
    by_sku = {item["sku"]: item for item in current}
    for item in update:
        if item["quantity"] <= 0:
            by_sku.pop(item["sku"], None)  # remove the line (if it exists)
        else:
            by_sku[item["sku"]] = item  # replace in place, or append if new
    return list(by_sku.values())


# endregion


# region typed_dict_state
class OrderDict(TypedDict):
    """Order state: two keys with reducers, the rest last-write-wins."""

    customer: str
    # merge_items combines every update with the stored cart.
    items: Annotated[list[LineItem], merge_items]
    tax_rate: float  # e.g. 0.2 for 20% VAT; the caller must pass it
    currency: str  # e.g. "EUR"; the caller must pass it
    subtotal: float  # written by compute_subtotal, replaced on each write
    total: float  # written by apply_tax, replaced on each write
    # operator.add concatenates lists: stored + update, so lines pile up.
    log: Annotated[list[str], operator.add]


# endregion


# region stock_node
def check_stock(state: OrderDict) -> dict[str, Any]:
    """Return only the lines above stock, capped; merge_items applies them."""
    changed: list[LineItem] = []
    for item in state["items"]:
        available = STOCK.get(item["sku"], 0)
        if item["quantity"] > available:
            changed.append({**item, "quantity": available})  # 0 means remove
    if not changed:
        # An empty list goes through merge_items too and changes nothing.
        return {"items": [], "log": ["check_stock: all in stock"]}
    old = {item["sku"]: item["quantity"] for item in state["items"]}
    notes = ", ".join(f"{c['sku']} {old[c['sku']]}->{c['quantity']}" for c in changed)
    # The log line is a one-element list: operator.add needs a list.
    return {"items": changed, "log": [f"check_stock: {notes}"]}


# endregion


# region bundle_node
def apply_bundle(state: OrderDict) -> dict[str, Any]:
    """Replace a cart that matches STARTER_KIT exactly with one kit line."""
    cart = {item["sku"]: item["quantity"] for item in state["items"]}
    if cart != STARTER_KIT:
        return {"log": ["apply_bundle: no bundle"]}
    # A plain [KIT_ITEM] would go through merge_items and be appended next
    # to PEN and NOTEBOOK. Overwrite skips the reducer and stores the value.
    return {
        "items": Overwrite([KIT_ITEM]),
        "log": ["apply_bundle: cart replaced by STARTER-KIT"],
    }


# endregion


# region typed_dict_nodes
def compute_subtotal(state: OrderDict) -> dict[str, Any]:
    """Sum quantity * unit_price over the cart into subtotal."""
    lines = (item["quantity"] * item["unit_price"] for item in state["items"])
    subtotal = round(sum(lines), 2)
    return {"subtotal": subtotal, "log": [f"compute_subtotal: {subtotal}"]}


def apply_tax(state: OrderDict) -> dict[str, Any]:
    """Add tax to subtotal and round the result into total."""
    total = round(state["subtotal"] * (1 + state["tax_rate"]), 2)
    return {"total": total, "log": [f"apply_tax: {total} {state['currency']}"]}


# endregion


# region typed_dict_graph
def build_graph() -> CompiledStateGraph:
    """Wire the four nodes into a linear graph and compile it."""
    # StateGraph reads the Annotated reducers from the schema and gives
    # those keys a channel that applies them.
    builder = StateGraph(OrderDict)
    builder.add_node("check_stock", check_stock)
    builder.add_node("apply_bundle", apply_bundle)
    builder.add_node("compute_subtotal", compute_subtotal)
    builder.add_node("apply_tax", apply_tax)
    builder.add_edge(START, "check_stock")
    builder.add_edge("check_stock", "apply_bundle")
    builder.add_edge("apply_bundle", "compute_subtotal")
    builder.add_edge("compute_subtotal", "apply_tax")
    builder.add_edge("apply_tax", END)
    return builder.compile()


# endregion

"""The order pipeline with shop settings in a run-scoped context.

START -> check_stock -> apply_bundle -> compute_subtotal -> apply_tax -> END

Four schemas and one context describe one graph:
- OrderDict is the graph's state schema: the shared keys and their reducers.
- OrderInput is what a caller sends; START writes only these keys.
- OrderOutput is the receipt; invoke returns only these keys.
- PricingState is private: apply_tax's parameter hint registers it, which
  adds the subtotal channel that no caller ever sends or receives.
- ShopContext is the run context: tax_rate and currency, passed per call
  with invoke(..., context=ShopContext(...)).

State changes from node to node and is returned; context is fixed for one
run and is never stored as a channel or returned.
"""

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
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
    # Shop settings (tax_rate, currency) live in ShopContext, not in the state.
    # No subtotal here: it lives in the private PricingState below.
    total: float  # written by apply_tax, replaced on each write
    # operator.add concatenates lists: stored + update, so lines pile up.
    log: Annotated[list[str], operator.add]


# endregion


# region io_schemas
# A key is ONE channel for the whole graph. OrderDict is registered first and
# gives items and log their reducers; a plain annotation here reuses them.
class OrderInput(TypedDict):
    """What a caller sends: just the cart."""

    customer: str
    items: list[LineItem]  # plain on purpose: still merged by merge_items


class OrderOutput(TypedDict):
    """The receipt: what invoke returns to the caller."""

    customer: str
    items: list[LineItem]
    total: float
    log: list[str]  # plain on purpose: still concatenated by operator.add


# endregion


# region private_schema
class PricingState(TypedDict):
    """Private pricing data passed from compute_subtotal to apply_tax.

    subtotal exists only here, so it is never in the input or the receipt.
    """

    subtotal: float


# endregion


# region shop_context
# No defaults: both fields are required, so a context dict with a missing or
# misspelled field fails loudly instead of pricing with a silent fallback.
# frozen=True because the context is read-only for the whole run; a value
# that nodes change belongs in the state.
@dataclass(frozen=True)
class ShopContext:
    """Shop settings for one run: read by nodes, never part of the state."""

    tax_rate: float  # e.g. 0.2 for 20% VAT
    currency: str  # e.g. "EUR"


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
    # A node may write any channel; its hint (OrderDict) only decides what it reads.
    return {"subtotal": subtotal, "log": [f"compute_subtotal: {subtotal}"]}


# The first parameter's hint is the node's input schema (return annotations
# are ignored). add_node registers PricingState's keys as channels, which is
# how "subtotal" exists at all; the node receives only that key.
# LangGraph injects the runtime by the parameter NAME "runtime" (any
# annotation is accepted, see KWARGS_CONFIG_KEYS in
# langgraph/_internal/_runnable.py). The Runtime[ShopContext] hint is for the
# reader and the type checker; runtime.context is what invoke(context=...) got.
def apply_tax(state: PricingState, runtime: Runtime[ShopContext]) -> dict[str, Any]:
    """Add the shop's tax to subtotal and round the result into total."""
    # runtime.context is the ShopContext of this run (None if none was passed).
    total = round(state["subtotal"] * (1 + runtime.context.tax_rate), 2)
    return {"total": total, "log": [f"apply_tax: {total} {runtime.context.currency}"]}


# endregion


# region typed_dict_graph
def build_graph() -> CompiledStateGraph:
    """Wire the four nodes into a linear graph and compile it."""
    # OrderDict is the shared state; input_schema filters what START writes
    # (unknown keys are dropped silently) and output_schema picks which
    # channels invoke returns. context_schema declares the shape of the run
    # context (the current API; config_schema= is deprecated, and your own
    # settings in config["configurable"] are the old pattern). It adds no channels.
    builder = StateGraph(
        OrderDict,
        input_schema=OrderInput,
        output_schema=OrderOutput,
        context_schema=ShopContext,
    )
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

"""Order checks: three independent checks run in parallel, one node joins them."""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

STOCK: dict[str, int] = {"PEN": 10, "NOTEBOOK": 2, "MUG": 0}
SHIPS_TO: set[str] = {"DE", "FR", "NL"}


# region order_state
class CheckResult(TypedDict):
    """The outcome of one check: which check, whether it passed, and why."""

    check: str  # "stock" | "payment" | "address"
    ok: bool
    detail: str


class OrderBase(TypedDict):
    """Every order key except ``results``, shared by both state schemas."""

    order_id: str
    items: dict[str, int]  # sku -> quantity
    total: float
    balance: float  # the customer's wallet
    address: str  # free text; the last comma-separated part is the country
    country: str  # written by normalize_address
    decision: str  # "approved" | "on_hold"
    problems: list[str]


class OrderState(OrderBase):
    """Order state where the parallel checks can all write ``results``.

    The ``operator.add`` reducer tells LangGraph how to merge several writes
    to the same key in one super-step: it concatenates the lists.
    """

    results: Annotated[list[CheckResult], operator.add]


# endregion


# region no_reducer_state
class NoReducerOrderState(OrderBase):
    """The same state without a reducer: only one write per step is allowed."""

    results: list[CheckResult]


# endregion


# region check_nodes
# The branch nodes are typed with OrderBase: they never read results, and
# LangGraph reads a node's type hint as its input schema. Hinting OrderState
# would register the reducer version of results even in a NoReducerOrderState
# graph, and add_node would refuse the clash.
def check_stock(state: OrderBase) -> dict:
    """Check that every line's quantity is in stock (unknown skus count as 0)."""
    short = [
        f"{sku} {qty}>{STOCK.get(sku, 0)}"
        for sku, qty in state["items"].items()
        if qty > STOCK.get(sku, 0)
    ]
    detail = ", ".join(short) or "all in stock"
    # A one-element list: the reducer appends it to what the other checks write.
    return {"results": [{"check": "stock", "ok": not short, "detail": detail}]}


def check_payment(state: OrderBase) -> dict:
    """Check that the customer's balance covers the order total."""
    balance, total = state["balance"], state["total"]
    ok = balance >= total
    detail = f"balance {balance} covers {total}" if ok else f"balance {balance} < total {total}"
    return {"results": [{"check": "payment", "ok": ok, "detail": detail}]}


# endregion


# region address_branch
def normalize_address(state: OrderBase) -> dict:
    """Extract the country code: the last comma-separated part, upper-cased."""
    return {"country": state["address"].rsplit(",", 1)[-1].strip().upper()}


def check_address(state: OrderBase) -> dict:
    """Check that we ship to the order's country (runs after normalize_address)."""
    country = state["country"]
    ok = country in SHIPS_TO
    detail = f"ships to {country}" if ok else f"no shipping to {country}"
    return {"results": [{"check": "address", "ok": ok, "detail": detail}]}


# endregion


# region decide_node
def decide(state: OrderState) -> dict:
    """Join the three checks into a decision, independent of their order.

    The order in which parallel writes land in ``results`` is not something
    to rely on, so look each result up by its check name and sort the names.
    """
    by_check = {r["check"]: r for r in state["results"]}
    problems = [
        f"{name}: {by_check[name]['detail']}"
        for name in sorted(by_check)
        if not by_check[name]["ok"]
    ]
    return {"decision": "on_hold" if problems else "approved", "problems": problems}


# endregion


# region build_graph
def build_graph(schema: type = OrderState) -> CompiledStateGraph:
    """Wire the fan-out from START and the join into decide, then compile."""
    builder = StateGraph(schema)
    builder.add_node("check_stock", check_stock)
    builder.add_node("check_payment", check_payment)
    builder.add_node("normalize_address", normalize_address)
    builder.add_node("check_address", check_address)
    # decide's hint says OrderState; input_schema=schema overrides it so the
    # same function also works in the NoReducerOrderState graph.
    builder.add_node("decide", decide, input_schema=schema)

    # Fan-out: three edges from START, so all three nodes run in super-step 1.
    builder.add_edge(START, "check_stock")
    builder.add_edge(START, "check_payment")
    builder.add_edge(START, "normalize_address")
    # The address branch is two nodes long: check_address runs in step 2.
    builder.add_edge("normalize_address", "check_address")
    # Join: a list of sources makes ONE waiting edge. decide runs only after
    # all three listed nodes have finished, however long each branch is.
    builder.add_edge(["check_stock", "check_payment", "check_address"], "decide")
    builder.add_edge("decide", END)
    return builder.compile()


# endregion

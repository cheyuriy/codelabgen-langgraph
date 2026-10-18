"""Order checks with the Functional API: tasks run concurrently, one entrypoint joins them.

The same checks as lesson 3.1, written as plain Python functions. There is no
state schema: data flows through function arguments and return values instead
of a shared state with reducers (compare 3.1's OrderState and its
``operator.add`` on ``results``).
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task

STOCK: dict[str, int] = {"PEN": 10, "NOTEBOOK": 2, "MUG": 0}
SHIPS_TO: set[str] = {"DE", "FR", "NL"}


# region order_types
class CheckResult(TypedDict):
    """The outcome of one check: which check, whether it passed, and why."""

    check: str  # "stock" | "payment" | "address"
    ok: bool
    detail: str


class Order(TypedDict):
    """The entrypoint's single input: everything one order needs."""

    order_id: str
    items: dict[str, int]  # sku -> quantity
    total: float
    balance: float  # the customer's wallet
    address: str  # free text; the last comma-separated part is the country


class OrderOutcome(TypedDict):
    """The entrypoint's return value, and all that the thread's state will hold."""

    order_id: str
    country: str
    decision: str  # "approved" | "on_hold"
    problems: list[str]


# endregion


# region check_tasks
# @task marks a function whose result is worth saving. Each task takes plain
# arguments, not the whole order: it gets only the data it needs.
@task
def check_stock(items: dict[str, int]) -> CheckResult:
    """Check that every line's quantity is in stock (unknown skus count as 0)."""
    short = [
        f"{sku} {qty}>{STOCK.get(sku, 0)}" for sku, qty in items.items() if qty > STOCK.get(sku, 0)
    ]
    detail = ", ".join(short) or "all in stock"
    return {"check": "stock", "ok": not short, "detail": detail}


@task
def check_payment(total: float, balance: float) -> CheckResult:
    """Check that the customer's balance covers the order total."""
    ok = balance >= total
    detail = f"balance {balance} covers {total}" if ok else f"balance {balance} < total {total}"
    return {"check": "payment", "ok": ok, "detail": detail}


# endregion


# region address_tasks
@task
def normalize_address(address: str) -> str:
    """Extract the country code: the last comma-separated part, upper-cased."""
    return address.rsplit(",", 1)[-1].strip().upper()


@task
def check_address(country: str) -> CheckResult:
    """Check that we ship to the order's country."""
    ok = country in SHIPS_TO
    detail = f"ships to {country}" if ok else f"no shipping to {country}"
    return {"check": "address", "ok": ok, "detail": detail}


# endregion


# region decide
# A plain function, not a task: pure, fast, deterministic code needs no task.
# Tasks are for work whose result is worth saving: I/O, slow or
# side-effecting calls.
def decide(results: list[CheckResult]) -> dict:
    """Join the check results into a decision and a sorted list of problems."""
    by_check = {r["check"]: r for r in results}
    problems = [
        f"{name}: {by_check[name]['detail']}"
        for name in sorted(by_check)
        if not by_check[name]["ok"]
    ]
    return {"decision": "on_hold" if problems else "approved", "problems": problems}


# endregion


# region process_order
# The checkpointer is fixed when the decorator runs, like
# compile(checkpointer=...) in 5.1.
checkpointer = InMemorySaver()


# @entrypoint turns the function into a Pregel graph (the same compiled object
# type as StateGraph.compile()) with one node named after the function, so
# invoke, stream and get_state work as in 5.1. The entrypoint takes exactly
# one positional input, so pass a dict. (9.2 adds `previous` and an approval
# interrupt.)
@entrypoint(checkpointer=checkpointer)
def process_order(order: Order) -> OrderOutcome:
    """Run the three order checks, stock and payment concurrently, and decide."""
    # Calling a task does not run it inline: it schedules it and returns a
    # concurrent.futures.Future at once. These two run at the same time in a
    # thread pool.
    stock = check_stock(order["items"])
    payment = check_payment(order["total"], order["balance"])
    # .result() blocks until that task is done. The address chain needs the
    # country first, while stock and payment keep running.
    country = normalize_address(order["address"]).result()
    address = check_address(country)
    results = [stock.result(), payment.result(), address.result()]
    return {"order_id": order["order_id"], "country": country, **decide(results)}


# endregion

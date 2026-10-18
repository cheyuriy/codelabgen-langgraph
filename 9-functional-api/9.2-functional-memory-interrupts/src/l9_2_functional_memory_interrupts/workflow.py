"""Order checks with the Functional API: tasks run concurrently, one entrypoint joins them.

The same checks as lesson 3.1, written as plain Python functions. There is no
state schema: data flows through function arguments and return values instead
of a shared state with reducers (compare 3.1's OrderState and its
``operator.add`` on ``results``).

Lesson 9.2 adds memory across runs (``previous`` and ``entrypoint.final``) and
a manager's approval through ``interrupt()`` for orders on hold.
"""

from collections import Counter
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import interrupt

STOCK: dict[str, int] = {"PEN": 10, "NOTEBOOK": 2, "MUG": 0}
SHIPS_TO: set[str] = {"DE", "FR", "NL"}


# region run_log
# How often each task's code really ran; the live run and the tests read it to
# show that resumed runs reuse saved results.
TASK_RUNS: Counter[str] = Counter()
# Stands in for an email service: the side effect this lesson keeps out of the
# entrypoint body.
OUTBOX: list[str] = []
# endregion


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
    # "approved" | "rejected" (on_hold is only a step before the manager answers)
    decision: str
    problems: list[str]


class DeskTally(TypedDict):
    """What the desk thread remembers between runs: the value previous receives."""

    orders: int
    approved: int
    rejected: int


# endregion


# region check_tasks
# @task marks a function whose result is worth saving. Each task takes plain
# arguments, not the whole order: it gets only the data it needs.
@task
def check_stock(items: dict[str, int]) -> CheckResult:
    """Check that every line's quantity is in stock (unknown skus count as 0)."""
    TASK_RUNS["check_stock"] += 1
    short = [
        f"{sku} {qty}>{STOCK.get(sku, 0)}" for sku, qty in items.items() if qty > STOCK.get(sku, 0)
    ]
    detail = ", ".join(short) or "all in stock"
    return {"check": "stock", "ok": not short, "detail": detail}


@task
def check_payment(total: float, balance: float) -> CheckResult:
    """Check that the customer's balance covers the order total."""
    TASK_RUNS["check_payment"] += 1
    ok = balance >= total
    detail = f"balance {balance} covers {total}" if ok else f"balance {balance} < total {total}"
    return {"check": "payment", "ok": ok, "detail": detail}


# endregion


# region address_tasks
@task
def normalize_address(address: str) -> str:
    """Extract the country code: the last comma-separated part, upper-cased."""
    TASK_RUNS["normalize_address"] += 1
    return address.rsplit(",", 1)[-1].strip().upper()


@task
def check_address(country: str) -> CheckResult:
    """Check that we ship to the order's country."""
    TASK_RUNS["check_address"] += 1
    ok = country in SHIPS_TO
    detail = f"ships to {country}" if ok else f"no shipping to {country}"
    return {"check": "address", "ok": ok, "detail": detail}


# endregion


# region notify_customer
# A side effect lives in a task: its result is saved in the checkpoint, so on
# resume the saved result is returned and the message is not sent a second
# time.
@task
def notify_customer(order_id: str, message: str) -> str:
    """Send the customer a message (here: append it to OUTBOX) and return it."""
    TASK_RUNS["notify_customer"] += 1
    note = f"to {order_id}: {message}"
    OUTBOX.append(note)
    return note


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
# one positional input, so pass a dict.
# `previous` is injected by LangGraph: it is keyword-only and found by its
# name. It holds what the last FINISHED run on this thread saved, and is None
# on a new thread.
# The annotation entrypoint.final[ReturnType, SaveType] names both types: what
# the caller gets and what the next run receives as `previous`.
@entrypoint(checkpointer=checkpointer)
def process_order(
    order: Order, *, previous: DeskTally | None = None
) -> entrypoint.final[OrderOutcome, DeskTally]:
    """Check the order, ask the manager when it is on hold, and count it on the desk tally."""
    # A print is a side effect too: left here on purpose to show that the body
    # replays on resume.
    print(f"  [process_order] body starts for {order['order_id']}, previous={previous}")
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
    outcome: OrderOutcome = {"order_id": order["order_id"], "country": country, **decide(results)}
    if outcome["decision"] == "on_hold":
        notify_customer(order["order_id"], "your order is waiting for review").result()
        # Same interrupt() and Command as 6.1; here the whole entrypoint is the
        # one node that pauses. The run stops here and is checkpointed.
        # Resuming with Command(resume=answer) on the same thread re-runs the
        # body from its first line: the tasks that finished before the pause
        # return their saved results without running, and interrupt() returns
        # the resume value instead of pausing. So everything before
        # interrupt() must take the same path again: no time, random or I/O
        # calls in the body, put them in a task.
        answer = interrupt(
            {
                "order_id": order["order_id"],
                "problems": outcome["problems"],
                "question": "approve or reject?",
            }
        )
        print(f"  [process_order] resumed with {answer!r}")
        outcome["decision"] = "approved" if answer == "approve" else "rejected"
    tally = previous or {"orders": 0, "approved": 0, "rejected": 0}
    tally = {
        **tally,
        "orders": tally["orders"] + 1,
        outcome["decision"]: tally[outcome["decision"]] + 1,
    }
    # value goes to the caller (and get_state().values); save goes to the
    # checkpoint and is what `previous` receives on the next run. Returning
    # the outcome directly would make `previous` the last outcome.
    return entrypoint.final(value=outcome, save=tally)


# endregion

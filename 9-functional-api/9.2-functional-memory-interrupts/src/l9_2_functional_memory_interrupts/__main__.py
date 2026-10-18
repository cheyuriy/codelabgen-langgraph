"""Live run: one desk thread reviews three orders, the manager answers the paused ones."""

from langgraph.types import Command

from l9_2_functional_memory_interrupts.workflow import (
    OUTBOX,
    TASK_RUNS,
    Order,
    checkpointer,
    process_order,
)

ADA: Order = {
    "order_id": "A-1001",
    "items": {"PEN": 4, "NOTEBOOK": 1},
    "total": 10.0,
    "balance": 50.0,
    "address": "12 Main St, Berlin, de",
}
BOB: Order = {
    "order_id": "B-1002",
    "items": {"PEN": 2, "MUG": 1},
    "total": 60.0,
    "balance": 20.0,
    "address": "5 Elm Rd, Leeds, uk",
}
CLEO: Order = {
    "order_id": "C-1003",
    "items": {"PEN": 1},
    "total": 1.5,
    "balance": 10.0,
    "address": "1 Rue Verte, Paris, us",
}

# One thread for the whole desk, not one per order, because `previous` is per
# thread: orders on the same thread share one tally.
DESK: dict = {"configurable": {"thread_id": "desk-1"}}
# The manager's fixed answers, so the run is deterministic.
ANSWERS: dict[str, str] = {"B-1002": "reject", "C-1003": "approve"}


# region review_order
def review(order: Order) -> None:
    """Run one order on the desk thread; if it pauses, resume it with the manager's answer."""
    print(f"== {order['order_id']} ==")
    TASK_RUNS.clear()
    # version="v2" returns a GraphOutput with .value and .interrupts (as in
    # 6.1). While the run is paused, out.value is still the PREVIOUS run's
    # return value (Ada's outcome when Bob pauses), so read out.interrupts,
    # not the value.
    out = process_order.invoke(order, DESK, version="v2")
    if out.interrupts:
        print(f"  paused, asks: {out.interrupts[0].value}")
        answer = ANSWERS[order["order_id"]]
        print(f"  manager answers {answer!r}")
        # The resume call passes no order: the input is restored from the
        # checkpoint.
        out = process_order.invoke(Command(resume=answer), DESK, version="v2")
    print(f"  -> {out.value['decision']}")
    print(f"  task runs: {dict(sorted(TASK_RUNS.items()))}")


# endregion


def main() -> None:
    """Review Ada's, Bob's and Cleo's orders on one thread, then show what it keeps."""
    # region desk_memory
    for order in (ADA, BOB, CLEO):
        review(order)
        print()
    print("== What the desk thread keeps ==")
    print(f"  outbox: {OUTBOX}")
    # get_state holds entrypoint.final's value.
    print(f"  get_state values: {process_order.get_state(DESK).values}")
    # save is stored in the "__previous__" channel of the latest checkpoint (an
    # internal channel name, read here only to show where save goes, like
    # "__return__" in 9.1).
    saved = checkpointer.get_tuple(DESK).checkpoint["channel_values"]["__previous__"]
    print(f"  saved for previous: {saved}")
    # endregion


if __name__ == "__main__":
    main()

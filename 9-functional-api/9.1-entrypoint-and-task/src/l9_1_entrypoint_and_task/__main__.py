"""Live run: process three orders and look at what the checkpointer saved."""

from l9_1_entrypoint_and_task.workflow import Order, checkpointer, process_order

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


def config_for(order: Order) -> dict:
    """One thread per order: the thread_id is the order id."""
    return {"configurable": {"thread_id": order["order_id"]}}


def show(value: object) -> str:
    """Render a CheckResult, an OrderOutcome or anything else as one short line."""
    if isinstance(value, dict) and "check" in value:
        return f"{value['check']}: {value['detail']}"
    if isinstance(value, dict) and "decision" in value:
        return str(value["decision"])
    return str(value)


def main() -> None:
    """Stream Ada's order, invoke Bob's and Cleo's, then inspect Ada's thread."""
    # region task_updates
    print("== Ada A-1001: one update per task ==")
    # Each task emits its own update when it finishes, keyed by the task's
    # function name, and the entrypoint emits its return value last.
    # Concurrent tasks finish in varying order, so the run sorts the names.
    updates: dict[str, object] = {}
    for chunk in process_order.stream(ADA, config_for(ADA), stream_mode="updates"):
        updates.update(chunk)
    for name in sorted(updates):
        print(f"  {name:<18} {show(updates[name])}")
    # endregion

    # region decisions
    print("\n== Decisions ==")
    for order in (BOB, CLEO):
        # invoke returns the entrypoint's return value.
        r = process_order.invoke(order, config_for(order))
        print(f"{r['order_id']} ({r['country']}) -> {r['decision']}")
        for problem in r["problems"]:
            print(f"    {problem}")
    # endregion

    # region saved_checkpoints
    print("\n== What the checkpointer saved for thread A-1001 ==")
    # The whole run is ONE super-step, so a run writes only two checkpoints
    # (3.1's StateGraph with a checkpointer would write five, steps -1..3).
    # pending_writes is a public field of CheckpointTuple holding
    # (task_id, channel, value) triples. "__return__" is the channel a task's
    # result is written to as soon as that task finishes, so the task results
    # hang on the "input" checkpoint as writes. The entrypoint's own
    # "__end__" and "__previous__" writes are skipped. Write order is
    # completion order, so the list is sorted.
    for cp in reversed(list(checkpointer.list(config_for(ADA)))):
        saved = sorted(show(w[2]) for w in cp.pending_writes or [] if w[1] == "__return__")
        print(f"  step {cp.metadata['step']:>2}  {cp.metadata['source']:<5}  task results: {saved}")
    # get_state holds only the return value, not the inputs or the
    # intermediate results (a StateGraph snapshot holds every state key).
    snap = process_order.get_state(config_for(ADA))
    print(f"  get_state values: {snap.values}")
    print(f"  next: {snap.next}")
    # endregion


if __name__ == "__main__":
    main()

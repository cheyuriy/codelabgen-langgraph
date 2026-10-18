"""Live run for lesson 6.3: the rules of interrupts.

Restarts and idempotent side effects, several interrupts in one node, and
parallel interrupts resumed by id.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, Interrupt

from l6_3_rules_of_interrupts.refunds import MANAGER_INBOX, NOTIFY_CALLS, build_graph
from l6_3_rules_of_interrupts.signoff import NODE_RUNS, build_signoff_graph


def config(request_id: str) -> dict[str, dict[str, str]]:
    """Return the run config for one refund request.

    One thread per refund request. The thread_id is how the resume call finds
    the paused run: the resume may come minutes or days later, from another
    request handler, and only needs to know this id.
    """
    return {"configurable": {"thread_id": f"refund-{request_id}"}}


def show_pending(interrupts: tuple[Interrupt, ...]) -> None:
    """Print how many interrupts are pending and who is asked what."""
    print(f"  pending interrupts: {len(interrupts)}")
    # The order of out.interrupts for parallel nodes is not stable (it changes
    # between runs), so sort for printing and pick by the "role" in the
    # payload, never by position.
    for item in sorted(interrupts, key=lambda i: i.value["role"]):
        print(f"    {item.value['role']}: {item.value['question']!r}")


def show_runs() -> None:
    """Print how many times each sign-off node has started so far."""
    print(
        f"  node runs: manager_signoff={NODE_RUNS['manager_signoff']} "
        f"finance_signoff={NODE_RUNS['finance_signoff']}"
    )


def main() -> None:
    """Show the rules of interrupts on the refund graph and the sign-off graph."""
    # Every invoke uses version="v2": it keeps the state (out.value) and the
    # pending interrupts (out.interrupts) apart.

    # region restart
    graph = build_graph(InMemorySaver())
    print("== R-2: $250, manager_review restarts on resume ==")
    graph.invoke({"request_id": "R-2", "amount": 250}, config("R-2"), version="v2")
    out = graph.invoke(Command(resume={"decision": "approve"}), config("R-2"), version="v2")
    # Two "started" lines mean two runs of the node, so the code before
    # interrupt() ran twice; the inbox still holds one message because
    # notify_manager is idempotent.
    print(f"  status={out.value['status']!r}")
    print(f"  notify_manager calls for R-2: {NOTIFY_CALLS['R-2']}")
    print(f"  manager inbox: {MANAGER_INBOX}")
    print()
    # endregion

    # region parallel_pause
    signoffs = build_signoff_graph(InMemorySaver())
    print("== R-6: $1500 needs a manager and finance, in parallel ==")
    out = signoffs.invoke({"request_id": "R-6", "amount": 1500}, config("R-6"), version="v2")
    show_pending(out.interrupts)
    show_runs()
    # With two pending interrupts LangGraph cannot know who a plain value is
    # for, so it refuses it; nothing runs and the thread stays paused.
    try:
        signoffs.invoke(Command(resume="approve"), config("R-6"), version="v2")
    except RuntimeError as error:
        print(f"  one plain value: RuntimeError: {str(error).split(' Docs:')[0]}")
    print()
    # endregion

    # region resume_by_id
    print("== R-6: resume both at once, keyed by Interrupt.id ==")
    answers = {"manager": "approve", "finance": "approve"}
    first_ids = {item.value["role"]: item.id for item in out.interrupts}
    # The map's keys are the ids of the pending interrupts and its values are
    # the answers, picked by the "role" in each payload, as in the guide's
    # resume_map.
    out = signoffs.invoke(
        Command(resume={item.id: answers[item.value["role"]] for item in out.interrupts}),
        config("R-6"),
        version="v2",
    )
    # finance_signoff got its answer and finished. manager_signoff restarted:
    # its first interrupt() returned "approve" and its second one paused, with
    # the same id, because both pauses belong to the same task.
    show_pending(out.interrupts)
    same_id = out.interrupts[0].id == first_ids["manager"]
    print(f"  same id as the manager's first question: {same_id}")
    show_runs()
    print()
    # endregion

    # region second_question
    print("== R-6: the manager's second question ==")
    # One pending interrupt, so a plain value is fine again. Only
    # manager_signoff runs again: finance_signoff finished in the previous
    # step and its result was saved, so its count stays at 2. The first
    # interrupt() replays "approve" and the second returns "duplicate charge",
    # matched by order.
    out = signoffs.invoke(Command(resume="duplicate charge"), config("R-6"), version="v2")
    show_pending(out.interrupts)
    show_runs()
    print(f"  status={out.value['status']!r} manager_reason={out.value['manager_reason']!r}")
    # endregion


if __name__ == "__main__":
    main()

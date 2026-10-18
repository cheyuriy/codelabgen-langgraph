"""Live run for lesson 6.2: approve, reject, edit and validate a manager's answer."""

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from l6_2_interrupt_patterns.refunds import build_graph


def config(request_id: str) -> dict[str, dict[str, str]]:
    """Return the run config for one refund request.

    One thread per refund request. The thread_id is how the resume call finds
    the paused run: the resume may come minutes or days later, from another
    request handler, and only needs to know this id.
    """
    return {"configurable": {"thread_id": f"refund-{request_id}"}}


def outcome(values: dict[str, Any]) -> str:
    """Format the final state of a refund request as one line."""
    return (
        f"  status={values['status']!r} decided_by={values['decided_by']!r} "
        f"approved_amount={values.get('approved_amount')}"
    )


def main() -> None:
    """Run five refund requests through the three interrupt patterns."""
    # The checkpointer is created here and passed in, so the same graph code
    # works with any saver (in memory here, SQLite or Postgres in a real app).
    graph = build_graph(InMemorySaver())
    # Every invoke uses version="v2": it keeps the state (out.value) and the
    # pending interrupts (out.interrupts) apart.

    # region small_refund
    print("== R-1: $40 is paid by policy ==")
    out = graph.invoke({"request_id": "R-1", "amount": 40}, config("R-1"), version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region approve
    print("== R-2: $250, the manager approves ==")
    out = graph.invoke({"request_id": "R-2", "amount": 250}, config("R-2"), version="v2")
    print(f"  question: {out.interrupts[0].value['question']!r}")
    # The resume value is now a dict, the answer a review form would post;
    # manager_review turns it into Command(goto="pay_refund").
    out = graph.invoke(Command(resume={"decision": "approve"}), config("R-2"), version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region reject
    print("== R-3: $500, the manager rejects ==")
    graph.invoke({"request_id": "R-3", "amount": 500}, config("R-3"), version="v2")
    # Same node, different answer, different next node: reject_refund runs
    # and pay_refund does not.
    out = graph.invoke(Command(resume={"decision": "reject"}), config("R-3"), version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region edit
    print("== R-4: $300, the manager approves $120 instead ==")
    graph.invoke({"request_id": "R-4", "amount": 300}, config("R-4"), version="v2")
    # The human edits the proposed value: pay_refund applies the edited
    # approved_amount, while amount still holds what was requested.
    out = graph.invoke(
        Command(resume={"decision": "approve", "amount": 120}), config("R-4"), version="v2"
    )
    print(outcome(out.value))
    print(f"  requested amount kept: {out.value['amount']}")
    print()
    # endregion

    # region validate
    print("== R-5: $180, invalid answers are asked again ==")
    out = graph.invoke({"request_id": "R-5", "amount": 180}, config("R-5"), version="v2")
    # Each bad answer leads to a new run of manager_review that asks again,
    # with the error in the payload; the caller just resumes the same thread
    # with the next answer.
    for answer in [
        "yes",
        {"decision": "approve", "amount": 900},
        {"decision": "approve", "amount": 150},
    ]:
        print(f"  answer: {answer!r}")
        out = graph.invoke(Command(resume=answer), config("R-5"), version="v2")
        if out.interrupts:
            print(f"  asked again: {out.interrupts[0].value['error']!r}")
    print(outcome(out.value))
    # endregion


if __name__ == "__main__":
    main()

"""Live run for lesson 6.1: pause a refund with interrupt(), resume it with Command."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from l6_1_interrupt_and_resume.refunds import build_graph


def config(request_id: str) -> dict[str, dict[str, str]]:
    """Return the run config for one refund request.

    One thread per refund request. The thread_id is how the resume call finds
    the paused run: the resume may come minutes or days later, from another
    request handler, and only needs to know this id.
    """
    return {"configurable": {"thread_id": f"refund-{request_id}"}}


def main() -> None:
    """Run three refund requests through the graph and show the pause and resume."""
    # The checkpointer is created here and passed in, so the same graph code
    # works with any saver (in memory here, SQLite or Postgres in a real app).
    graph = build_graph(InMemorySaver())

    # region small_refund
    print("== R-1: $40 is within the $100 limit ==")
    result = graph.invoke({"request_id": "R-1", "amount": 40}, config("R-1"))
    print(f"  status={result['status']!r} decided_by={result['decided_by']!r}")
    print(f"  paused: {'__interrupt__' in result}")
    print()
    # endregion

    # region pause
    print("== R-2: $250 pauses for the manager (v1 output) ==")
    # In the default v1 format, invoke does not raise when the graph pauses.
    # It returns the state so far plus an "__interrupt__" key holding a list
    # of Interrupt objects (fields: value, id, response_schema). "status" is
    # missing because manager_review has not returned yet.
    result = graph.invoke({"request_id": "R-2", "amount": 250}, config("R-2"))
    print(f"  keys: {sorted(result)}")
    pending = result["__interrupt__"]
    print(f"  pending interrupts: {len(pending)}")
    print(f"  payload: {pending[0].value}")
    # The id is a long generated string; print only whether it is set.
    print(f"  interrupt id set: {bool(pending[0].id)}")
    print()
    # endregion

    # region pending_state
    print("== get_state while paused ==")
    # This is how a separate process (say a web handler showing the manager's
    # inbox) finds pending requests without the invoke result: it loads the
    # thread's latest checkpoint. `next` names the node that will run again,
    # `interrupts` lists the interrupts still waiting for an answer, and
    # `tasks[i].interrupts` holds the same interrupts per task.
    snap = graph.get_state(config("R-2"))
    print(f"  next: {snap.next}")
    print(f"  values: {snap.values}")
    print(
        f"  snap.interrupts: {len(snap.interrupts)}  "
        f"question: {snap.interrupts[0].value['question']!r}"
    )
    task = snap.tasks[0]
    print(f"  tasks[0]: name={task.name!r} interrupts={len(task.interrupts)}")
    same = pending[0].id == snap.interrupts[0].id == task.interrupts[0].id
    print(f"  same interrupt everywhere: {same}")
    print()
    # endregion

    # region resume
    print("== Resume R-2 with Command(resume='approved') ==")
    # A Command is passed in place of the input. The same thread_id is what
    # makes this a resume of R-2. manager_review prints "started" a second
    # time because it re-runs from its top; this time interrupt() returns
    # "approved" instead of pausing.
    result = graph.invoke(Command(resume="approved"), config("R-2"))
    print(f"  status={result['status']!r} decided_by={result['decided_by']!r}")
    snap = graph.get_state(config("R-2"))
    print(f"  next: {snap.next}  interrupts: {len(snap.interrupts)}")
    print()
    # endregion

    # region output_v2
    print("== R-3: $500 with version='v2' ==")
    # version="v2" (new in 1.1, opt-in) returns a GraphOutput: .value is the
    # state (it never contains "__interrupt__") and .interrupts is a tuple,
    # empty when the run finished. out["key"] still works on a GraphOutput
    # but emits LangGraphDeprecatedSinceV11, so always use .value and
    # .interrupts.
    out = graph.invoke({"request_id": "R-3", "amount": 500}, config("R-3"), version="v2")
    print(f"  {type(out).__name__}: value={out.value} interrupts={len(out.interrupts)}")
    print(f"  question: {out.interrupts[0].value['question']!r}")
    out = graph.invoke(Command(resume="rejected"), config("R-3"), version="v2")
    print(f"  {type(out).__name__}: value={out.value} interrupts={len(out.interrupts)}")
    # endregion


if __name__ == "__main__":
    main()

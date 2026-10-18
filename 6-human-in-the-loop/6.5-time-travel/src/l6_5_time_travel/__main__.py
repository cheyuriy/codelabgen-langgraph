"""Live run for lesson 6.5: walk back through one refund thread, replay it from
two past checkpoints and fork it with update_state."""

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, StateSnapshot

from l6_5_time_travel.refunds import build_graph


def config(request_id: str) -> dict[str, dict[str, str]]:
    """Return the run config for one refund request.

    One thread per refund request. The thread_id is how the resume call finds
    the paused run: the resume may come minutes or days later, from another
    request handler, and only needs to know this id.
    """
    return {"configurable": {"thread_id": f"refund-{request_id}"}}


# region at_checkpoint
def at_checkpoint(request_id: str, checkpoint_id: str) -> dict[str, dict[str, str]]:
    """Return the config of one saved checkpoint of the request's thread."""
    # A snapshot's .config already holds these three keys. This helper shows
    # what is inside, the way an app builds it when it stored only the
    # checkpoint_id (in an audit log, in a URL).
    return {
        "configurable": {
            "thread_id": f"refund-{request_id}",
            # "" is the namespace of the top-level graph. Keep it:
            # update_state with InMemorySaver fails with KeyError
            # 'checkpoint_ns' without it (invoke does not).
            "checkpoint_ns": "",
            # Which saved checkpoint of the thread to start from.
            "checkpoint_id": checkpoint_id,
        }
    }


# endregion


def outcome(values: dict[str, Any]) -> str:
    """Format the final state of a refund request as one line."""
    return (
        f"  status={values['status']!r} decided_by={values['decided_by']!r} "
        f"approved_amount={values.get('approved_amount')}"
    )


# region describe_checkpoint
def describe(snap: StateSnapshot) -> str:
    """Describe one checkpoint as one line.

    Step and source come from the checkpoint's metadata, then the nodes that
    run next, then the refund fields of the saved state.
    """
    # Never print the checkpoint_id (time-based, different on every run) or
    # created_at: the output would change on every run.
    md, values = snap.metadata, snap.values
    return (
        f"  step {md['step']:>2}  {md['source']:<6}  next={snap.next!s:<20}  "
        f"amount={values.get('amount')}  approved_amount={values.get('approved_amount')}  "
        f"status={values.get('status')}"
    )


# endregion


def main() -> None:
    """Run one refund thread, then replay and fork it from past checkpoints."""
    # The graph is exactly 6.2's: time travel is an API of the caller, not of
    # the graph. It only needs a checkpointer, which keeps every checkpoint.
    graph = build_graph(InMemorySaver())
    thread = config("R-4")
    # Every invoke uses version="v2": it keeps the state (out.value) and the
    # pending interrupts (out.interrupts) apart.

    # region original_run
    print("== R-4: the original run, the manager approves $120 of $300 ==")
    # Exactly 6.2's edit case. This one thread is what the rest of the run
    # travels through.
    graph.invoke({"request_id": "R-4", "amount": 300}, thread, version="v2")
    out = graph.invoke(Command(resume={"decision": "approve", "amount": 120}), thread, version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region history
    print("== get_state_history: the checkpoints of the thread, newest first ==")
    # The same StateSnapshot as get_state (5.1), one per saved checkpoint,
    # newest first: the input checkpoint at step -1, then one per super-step.
    # The pause did not add a checkpoint: step 0 is where manager_review
    # paused, and the resume continued from it.
    history = list(graph.get_state_history(thread))
    for snap in history:
        print(describe(snap))
    # Pick a checkpoint by what it was about to do (next), never by its
    # position in the list: once the thread branches, positions and step
    # numbers repeat.
    paused = next(s for s in history if s.next == ("manager_review",))
    before_pay = next(s for s in history if s.next == ("pay_refund",))
    paused_id = paused.config["configurable"]["checkpoint_id"]
    before_pay_id = before_pay.config["configurable"]["checkpoint_id"]
    print(
        f"  {len(history)} checkpoints; picked step {paused.metadata['step']} "
        f"(before manager_review) and step {before_pay.metadata['step']} (before pay_refund)"
    )
    print()
    # endregion

    # region replay_after_decision
    print("== Replay from step 1: manager_review is not run again, pay_refund is ==")
    # Input None plus a config with a checkpoint_id means "continue from this
    # past checkpoint": a replay. manager_review ran before this checkpoint
    # and its result (decided_by, approved_amount) is saved in it, so it does
    # not run again and the manager is not asked. pay_refund comes after it
    # and really runs again: the refund is paid twice. Replay re-executes
    # nodes, it is not a cached re-read, so side effects after the
    # checkpoint must be idempotent (6.3).
    out = graph.invoke(None, at_checkpoint("R-4", before_pay_id), version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region replay_before_decision
    print("== Replay from step 0: manager_review runs again and asks again ==")
    # Step 0 is where manager_review paused. Replaying it runs the node from
    # its top, and interrupt() pauses again: the $120 answer from the
    # original run is not reused, so a different answer can be given.
    out = graph.invoke(None, at_checkpoint("R-4", paused_id), version="v2")
    print(f"  asked again: {out.interrupts[0].value['question']!r}")
    # Resume with the plain thread config: the replay's new checkpoint is now
    # the newest one of the thread, so the resume finds the new pause. Do not
    # resume through at_checkpoint(paused_id) (see the experiments).
    out = graph.invoke(Command(resume={"decision": "reject"}), thread, version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region kept_history
    print("== get_state_history after two replays: old checkpoints are kept ==")
    # Each replay started with a "fork" checkpoint (a copy of the chosen one,
    # one step later) and continued from there. Nothing was deleted or
    # overwritten, so the original approved run is still listed. The list is
    # ordered by time across all branches, so step numbers repeat.
    for snap in graph.get_state_history(thread):
        print(describe(snap))
    # get_state(thread) always reads the newest checkpoint of the thread.
    newest = graph.get_state(thread)
    print(f"  get_state(thread) reads the newest: status={newest.values['status']!r}")
    print()
    # endregion

    # region fork_with_update
    print("== Fork from step 0: update_state(amount=250), no as_node ==")
    # The customer corrected the request to $250. update_state does not
    # change the past checkpoint: it writes a new one (source "update") whose
    # parent is step 0, and returns its config.
    fork = graph.update_state(at_checkpoint("R-4", paused_id), {"amount": 250})
    snap = graph.get_state(fork)
    print(describe(snap))
    print(
        "  parent is the step 0 checkpoint: "
        f"{snap.parent_config['configurable']['checkpoint_id'] == paused_id}"
    )
    # Without as_node the update is applied as the node that wrote last
    # before step 0, which is the input (__start__). So START's conditional
    # edge route_by_amount runs again: $250 is still above the limit, and
    # next is manager_review. Its interrupt fires again in the fork, and the
    # fork is resumed on the thread like any pause.
    out = graph.invoke(None, fork, version="v2")
    print(f"  asked: {out.interrupts[0].value['question']!r}")
    out = graph.invoke(Command(resume={"decision": "approve"}), thread, version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region fork_as_node
    print("== Fork from step 0 with as_node: the node named decides what runs next ==")
    # as_node says which node the update pretends to come from; the graph
    # then continues along that node's edges. manager_review routes only with
    # Command(goto=...) and has no static edge, so a plain dict "from" it
    # leads nowhere: next is () and nothing would be paid. auto_approve has
    # the edge auto_approve -> pay_refund, so the policy pays $300 and
    # manager_review (with its interrupt) is skipped.
    decision = {"decided_by": "policy", "approved_amount": 300}
    for node in ["manager_review", "auto_approve"]:
        fork = graph.update_state(at_checkpoint("R-4", paused_id), decision, as_node=node)
        print(f"  as_node={node!r}: next={graph.get_state(fork).next}")
    # The last fork (auto_approve) is the one continued.
    out = graph.invoke(None, fork, version="v2")
    print(outcome(out.value))
    print()
    # endregion

    # region all_branches
    print("== Every branch is still in the thread ==")
    # Six branch ends from one request: the auto_approve fork, the
    # manager_review fork that never paid, the $250 fork, the rejected
    # replay, the step 1 replay, and the original run.
    history = list(graph.get_state_history(thread))
    ends = [
        (s.values.get("status"), s.values.get("approved_amount")) for s in history if not s.next
    ]
    print(f"  {len(history)} checkpoints, {len(ends)} of them with nothing left to run")
    print(f"  (status, approved_amount) at those ends, newest first: {ends}")
    # endregion


if __name__ == "__main__":
    main()

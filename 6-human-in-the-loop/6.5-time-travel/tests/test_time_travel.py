"""Offline tests for lesson 6.5: state history, replay and forks of one refund thread."""

from typing import Any

import pytest
from l6_5_time_travel import refunds
from l6_5_time_travel.refunds import build_graph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import InvalidUpdateError
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot

THREAD: dict[str, Any] = {"configurable": {"thread_id": "refund-R-4"}}


def checkpoint_id(config: Any) -> str:
    """Return the checkpoint_id of a config (never compared to a fixed value)."""
    return config["configurable"]["checkpoint_id"]


def summary(graph: CompiledStateGraph) -> list[tuple[int, str, tuple[str, ...]]]:
    """Return (step, source, next) of every checkpoint of the thread, newest first."""
    return [
        (s.metadata["step"], s.metadata["source"], s.next) for s in graph.get_state_history(THREAD)
    ]


def original_run() -> tuple[CompiledStateGraph, list[StateSnapshot], StateSnapshot, StateSnapshot]:
    """Run R-4 once (the manager approves $120 of $300) and pick two past checkpoints."""
    graph = build_graph(InMemorySaver())
    graph.invoke({"request_id": "R-4", "amount": 300}, THREAD, version="v2")
    graph.invoke(Command(resume={"decision": "approve", "amount": 120}), THREAD, version="v2")
    history = list(graph.get_state_history(THREAD))
    paused = next(s for s in history if s.next == ("manager_review",))
    before_pay = next(s for s in history if s.next == ("pay_refund",))
    return graph, history, paused, before_pay


def test_history_of_the_original_run() -> None:
    """get_state_history lists the four checkpoints newest first, linked by parent."""
    graph, history, paused, before_pay = original_run()
    assert [(s.metadata["step"], s.metadata["source"], s.next) for s in history] == [
        (2, "loop", ()),
        (1, "loop", ("pay_refund",)),
        (0, "loop", ("manager_review",)),
        (-1, "input", ("__start__",)),
    ]
    assert history[0].values["status"] == "approved"
    assert history[0].values["approved_amount"] == 120
    assert before_pay.values["approved_amount"] == 120
    assert "status" not in before_pay.values
    assert "decided_by" not in paused.values

    # Each snapshot points at the next older one; the input checkpoint has no parent.
    for newer, older in zip(history, history[1:], strict=False):
        assert checkpoint_id(newer.parent_config) == checkpoint_id(older.config)
    assert history[-1].parent_config is None
    assert len({checkpoint_id(s.config) for s in history}) == 4
    assert all(set(s.metadata) == {"source", "step", "parents"} for s in history)

    past = graph.get_state(
        {
            "configurable": {
                "thread_id": "refund-R-4",
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id(paused.config),
            }
        }
    )
    assert past.next == ("manager_review",)
    assert past.metadata["step"] == 0


def test_replay_after_decision_reruns_only_what_follows(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replaying from before pay_refund pays again but does not ask the manager."""
    graph, history, paused, before_pay = original_run()
    # Count check_answer calls: manager_review looks the name up in the module
    # at call time, so patching the module attribute is enough.
    calls: list[Any] = []
    original_check = refunds.check_answer

    def counting_check(answer: Any, requested: int) -> str | None:
        calls.append(answer)
        return original_check(answer, requested)

    monkeypatch.setattr(refunds, "check_answer", counting_check)
    capsys.readouterr()

    out = graph.invoke(None, before_pay.config, version="v2")
    assert capsys.readouterr().out.splitlines() == ["  [pay_refund] paying $120 for R-4"]
    assert len(calls) == 0
    assert out.value["status"] == "approved"
    assert out.interrupts == ()

    steps = summary(graph)
    assert len(steps) == 6
    assert steps[:2] == [(3, "loop", ()), (2, "fork", ("pay_refund",))]
    fork = list(graph.get_state_history(THREAD))[1]
    assert checkpoint_id(fork.parent_config) == checkpoint_id(before_pay.config)


def test_replay_before_decision_asks_again(capsys: pytest.CaptureFixture[str]) -> None:
    """Replaying the paused checkpoint runs manager_review again and it pauses again."""
    graph, history, paused, before_pay = original_run()
    capsys.readouterr()

    out = graph.invoke(None, paused.config, version="v2")
    assert capsys.readouterr().out.splitlines() == ["  [manager_review] started for R-4"]
    assert len(out.interrupts) == 1
    assert out.interrupts[0].value["question"] == "Approve a refund of $300 for R-4?"
    assert out.value == {"request_id": "R-4", "amount": 300}

    head = graph.get_state(THREAD)
    assert head.next == ("manager_review",)
    assert head.metadata["source"] == "fork"
    assert head.metadata["step"] == 1
    assert checkpoint_id(head.parent_config) == checkpoint_id(paused.config)

    # A different answer than in the original run, resumed on the plain thread.
    out = graph.invoke(Command(resume={"decision": "reject"}), THREAD, version="v2")
    assert out.value["status"] == "rejected"
    ends = [s.values.get("status") for s in graph.get_state_history(THREAD) if not s.next]
    assert ends == ["rejected", "approved"]
    assert len(summary(graph)) == 7


def test_fork_without_as_node() -> None:
    """update_state from step 0 counts as input: route_by_amount runs again."""
    graph, history, paused, before_pay = original_run()
    fork = graph.update_state(paused.config, {"amount": 250})
    snap = graph.get_state(fork)
    assert snap.metadata["source"] == "update"
    assert snap.metadata["step"] == 1
    assert snap.next == ("manager_review",)
    assert checkpoint_id(snap.parent_config) == checkpoint_id(paused.config)
    assert snap.values == {"request_id": "R-4", "amount": 250}

    out = graph.invoke(None, fork, version="v2")
    assert out.interrupts[0].value["question"] == "Approve a refund of $250 for R-4?"
    out = graph.invoke(Command(resume={"decision": "approve"}), THREAD, version="v2")
    assert out.value["status"] == "approved"
    assert out.value["approved_amount"] == 250
    # The original branch is still there, untouched.
    assert any(
        not s.next and s.values.get("approved_amount") == 120
        for s in graph.get_state_history(THREAD)
    )

    small = graph.update_state(paused.config, {"amount": 90})
    assert graph.get_state(small).next == ("auto_approve",)


def test_as_node_picks_the_next_node(capsys: pytest.CaptureFixture[str]) -> None:
    """The node named in as_node decides which edges the fork follows."""
    graph, history, paused, before_pay = original_run()
    decision = {"decided_by": "policy", "approved_amount": 300}

    dead_end = graph.update_state(paused.config, decision, as_node="manager_review")
    assert graph.get_state(dead_end).next == ()

    fork = graph.update_state(paused.config, decision, as_node="auto_approve")
    snap = graph.get_state(fork)
    assert snap.next == ("pay_refund",)
    assert snap.metadata["source"] == "update"

    capsys.readouterr()
    out = graph.invoke(None, fork, version="v2")
    assert capsys.readouterr().out.splitlines() == ["  [pay_refund] paying $300 for R-4"]
    assert out.value == {
        "request_id": "R-4",
        "amount": 300,
        "status": "approved",
        "decided_by": "policy",
        "approved_amount": 300,
    }

    with pytest.raises(InvalidUpdateError, match="Node nope does not exist"):
        graph.update_state(paused.config, decision, as_node="nope")

    # Inferred as_node at step 1 is manager_review, which has no static edge.
    nothing = graph.update_state(before_pay.config, {"approved_amount": 150})
    assert graph.get_state(nothing).next == ()

"""Offline tests for lesson 6.3: restarts, idempotent side effects, parallel interrupts."""

from collections.abc import Iterator

import pytest
from l6_3_rules_of_interrupts import refunds, signoff
from l6_3_rules_of_interrupts.refunds import build_graph
from l6_3_rules_of_interrupts.signoff import build_signoff_graph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def config(request_id: str) -> dict[str, dict[str, str]]:
    """Return the per-request thread config used by the lesson."""
    return {"configurable": {"thread_id": f"refund-{request_id}"}}


@pytest.fixture(autouse=True)
def clear_module_state() -> Iterator[None]:
    """Reset the module-level counters and inbox before each test."""
    refunds.NOTIFY_CALLS.clear()
    refunds.MANAGER_INBOX.clear()
    signoff.NODE_RUNS.clear()
    yield


def test_restart_runs_notification_twice_but_sends_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """manager_review restarts on resume; notify_manager is idempotent."""
    graph = build_graph(InMemorySaver())
    graph.invoke({"request_id": "R-2", "amount": 250}, config("R-2"), version="v2")
    out = graph.invoke(Command(resume={"decision": "approve"}), config("R-2"), version="v2")

    printed = capsys.readouterr().out
    assert printed.count("[manager_review] started for R-2") == 2
    assert refunds.NOTIFY_CALLS["R-2"] == 2
    assert refunds.MANAGER_INBOX == ["Refund R-2 for $250 waits for your review"]
    assert out.value["status"] == "approved"


def test_reask_loop_reruns_code_before_interrupt() -> None:
    """Each re-ask through the graph re-enters manager_review and re-notifies."""
    graph = build_graph(InMemorySaver())
    graph.invoke({"request_id": "R-5", "amount": 180}, config("R-5"), version="v2")
    graph.invoke(Command(resume="yes"), config("R-5"), version="v2")
    out = graph.invoke(
        Command(resume={"decision": "approve", "amount": 150}), config("R-5"), version="v2"
    )

    assert refunds.NOTIFY_CALLS["R-5"] == 4
    assert refunds.MANAGER_INBOX == ["Refund R-5 for $180 waits for your review"]
    assert out.value["status"] == "approved"
    assert out.value["approved_amount"] == 150


def test_parallel_pause_refuses_plain_resume() -> None:
    """Two sign-offs pause together; a plain resume value is refused."""
    graph = build_signoff_graph(InMemorySaver())
    out = graph.invoke({"request_id": "R-6", "amount": 1500}, config("R-6"), version="v2")

    assert len(out.interrupts) == 2
    assert {i.value["role"] for i in out.interrupts} == {"manager", "finance"}
    first, second = out.interrupts
    assert first.id != second.id
    assert set(graph.get_state(config("R-6")).next) == {"manager_signoff", "finance_signoff"}

    with pytest.raises(RuntimeError, match="multiple pending interrupts"):
        graph.invoke(Command(resume="approve"), config("R-6"), version="v2")

    assert set(graph.get_state(config("R-6")).next) == {"manager_signoff", "finance_signoff"}
    assert signoff.NODE_RUNS == {"manager_signoff": 1, "finance_signoff": 1}


def test_id_map_then_second_question_in_order() -> None:
    """An id map answers both pauses; the manager's second answer matches by order."""
    graph = build_signoff_graph(InMemorySaver())
    out = graph.invoke({"request_id": "R-6", "amount": 1500}, config("R-6"), version="v2")
    answers = {"manager": "approve", "finance": "approve"}
    first_ids = {i.value["role"]: i.id for i in out.interrupts}

    out = graph.invoke(
        Command(resume={i.id: answers[i.value["role"]] for i in out.interrupts}),
        config("R-6"),
        version="v2",
    )
    assert len(out.interrupts) == 1
    pending = out.interrupts[0]
    assert pending.value["role"] == "manager"
    assert pending.value["question"] == "You chose 'approve'. Why? (kept in the audit log)"
    assert pending.id == first_ids["manager"]
    assert out.value["finance_decision"] == "approve"
    assert "manager_decision" not in out.value
    assert signoff.NODE_RUNS["manager_signoff"] == 2
    assert signoff.NODE_RUNS["finance_signoff"] == 2

    out = graph.invoke(Command(resume="duplicate charge"), config("R-6"), version="v2")
    assert out.interrupts == ()
    assert out.value["status"] == "approved"
    assert out.value["manager_decision"] == "approve"
    assert out.value["manager_reason"] == "duplicate charge"
    assert signoff.NODE_RUNS["manager_signoff"] == 3
    assert signoff.NODE_RUNS["finance_signoff"] == 2


def test_both_signoffs_must_approve(capsys: pytest.CaptureFixture[str]) -> None:
    """A finance reject rejects the refund even when the manager approves."""
    graph = build_signoff_graph(InMemorySaver())
    out = graph.invoke({"request_id": "R-6", "amount": 1500}, config("R-6"), version="v2")
    answers = {"manager": "approve", "finance": "reject"}
    graph.invoke(
        Command(resume={i.id: answers[i.value["role"]] for i in out.interrupts}),
        config("R-6"),
        version="v2",
    )
    out = graph.invoke(Command(resume="over budget"), config("R-6"), version="v2")

    assert out.value["status"] == "rejected"
    assert "[settle] R-6 rejected" in capsys.readouterr().out

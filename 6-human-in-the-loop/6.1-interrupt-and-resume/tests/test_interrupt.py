"""Offline tests for lesson 6.1: interrupt() pauses, Command(resume=...) resumes."""

import warnings

import pytest
from l6_1_interrupt_and_resume.refunds import build_graph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, GraphOutput, Interrupt


def config(request_id: str) -> dict[str, dict[str, str]]:
    """Return the per-request thread config used by the lesson."""
    return {"configurable": {"thread_id": f"refund-{request_id}"}}


R2_PAYLOAD = {
    "request_id": "R-2",
    "amount": 250,
    "question": "Approve a refund of $250 for R-2?",
}


def test_small_refund_does_not_pause() -> None:
    """A refund within the limit is approved by policy and finishes the run."""
    graph = build_graph(InMemorySaver())
    result = graph.invoke({"request_id": "R-1", "amount": 40}, config("R-1"))
    assert "__interrupt__" not in result
    assert result["status"] == "approved"
    assert result["decided_by"] == "policy"

    snap = graph.get_state(config("R-1"))
    assert snap.next == ()
    assert snap.interrupts == ()


def test_large_refund_pauses() -> None:
    """A refund above the limit pauses in manager_review with the payload."""
    graph = build_graph(InMemorySaver())
    result = graph.invoke({"request_id": "R-2", "amount": 250}, config("R-2"))
    pending = result["__interrupt__"]
    assert len(pending) == 1
    assert isinstance(pending[0], Interrupt)
    assert pending[0].value == R2_PAYLOAD
    assert "status" not in result

    snap = graph.get_state(config("R-2"))
    assert snap.next == ("manager_review",)
    assert snap.values == {"request_id": "R-2", "amount": 250}
    assert len(snap.interrupts) == 1
    assert snap.tasks[0].name == "manager_review"
    assert pending[0].id == snap.interrupts[0].id == snap.tasks[0].interrupts[0].id


def test_resume_uses_the_human_value(capsys: pytest.CaptureFixture[str]) -> None:
    """Command(resume=...) becomes interrupt()'s return value; the node re-runs."""
    graph = build_graph(InMemorySaver())
    graph.invoke({"request_id": "R-2", "amount": 250}, config("R-2"))
    result = graph.invoke(Command(resume="approved"), config("R-2"))
    assert result["status"] == "approved"
    assert result["decided_by"] == "manager"

    snap = graph.get_state(config("R-2"))
    assert snap.next == ()
    assert snap.interrupts == ()
    assert snap.tasks == ()

    out = capsys.readouterr().out
    assert out.count("[manager_review] started for R-2") == 2
    assert out.count("[manager_review] resumed with ") == 1


def test_v2_output_format() -> None:
    """version='v2' returns a GraphOutput with .value and .interrupts, no warnings."""
    graph = build_graph(InMemorySaver())
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        out = graph.invoke({"request_id": "R-3", "amount": 500}, config("R-3"), version="v2")
        assert isinstance(out, GraphOutput)
        assert out.value == {"request_id": "R-3", "amount": 500}
        assert isinstance(out.interrupts, tuple)
        assert len(out.interrupts) == 1
        assert out.interrupts[0].value["question"] == "Approve a refund of $500 for R-3?"

        out = graph.invoke(Command(resume="rejected"), config("R-3"), version="v2")
        assert out.value["status"] == "rejected"
        assert out.value["decided_by"] == "manager"
        assert out.interrupts == ()


def test_resume_needs_a_checkpointer() -> None:
    """Without a checkpointer the pause is reported but cannot be resumed."""
    graph = build_graph(None)
    result = graph.invoke({"request_id": "R-2", "amount": 250})
    assert len(result["__interrupt__"]) == 1
    with pytest.raises(RuntimeError, match="without checkpointer"):
        graph.invoke(Command(resume="approved"), config("R-2"))

    checkpointed = build_graph(InMemorySaver())
    with pytest.raises(ValueError, match="thread_id"):
        checkpointed.invoke({"request_id": "R-2", "amount": 250})

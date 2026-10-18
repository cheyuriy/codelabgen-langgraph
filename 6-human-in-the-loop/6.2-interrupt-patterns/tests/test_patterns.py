"""Offline tests for lesson 6.2: approve/reject routing, edited amounts, validation."""

from typing import Any

import pytest
from l6_2_interrupt_patterns import refunds
from l6_2_interrupt_patterns.refunds import build_graph, check_answer
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

DECISION_ERROR = "decision must be 'approve' or 'reject'"


def config(request_id: str) -> dict[str, dict[str, str]]:
    """Return the per-request thread config used by the lesson."""
    return {"configurable": {"thread_id": f"refund-{request_id}"}}


def test_check_answer() -> None:
    """check_answer accepts well-formed answers and explains the rest."""
    assert check_answer({"decision": "approve"}, 300) is None
    assert check_answer({"decision": "reject"}, 300) is None
    assert check_answer({"decision": "approve", "amount": 120}, 300) is None
    assert check_answer({"decision": "approve", "amount": 300}, 300) is None

    for bad in ["yes", {}, {"decision": "maybe"}]:
        assert check_answer(bad, 300) == DECISION_ERROR

    for amount in [0, 900, "120"]:
        answer = {"decision": "approve", "amount": amount}
        assert check_answer(answer, 300) == "amount must be a whole number from 1 to 300"


def test_approve_and_reject_route_differently(capsys: pytest.CaptureFixture[str]) -> None:
    """The manager's decision picks pay_refund or reject_refund."""
    graph = build_graph(InMemorySaver())
    assert graph.builder.nodes["manager_review"].ends == (
        "pay_refund",
        "reject_refund",
        "manager_review",
    )

    graph.invoke({"request_id": "R-2", "amount": 250}, config("R-2"), version="v2")
    out = graph.invoke(Command(resume={"decision": "approve"}), config("R-2"), version="v2")
    assert out.value["status"] == "approved"
    assert out.value["decided_by"] == "manager"
    assert out.value["approved_amount"] == 250

    graph.invoke({"request_id": "R-3", "amount": 500}, config("R-3"), version="v2")
    out = graph.invoke(Command(resume={"decision": "reject"}), config("R-3"), version="v2")
    assert out.value["status"] == "rejected"
    assert out.value["decided_by"] == "manager"
    assert "approved_amount" not in out.value

    printed = capsys.readouterr().out
    assert "[pay_refund] paying $250 for R-2" in printed
    assert "[reject_refund] no refund for R-3" in printed
    pay_lines = [line for line in printed.splitlines() if "[pay_refund]" in line]
    assert not any("R-3" in line for line in pay_lines)


def test_edited_amount_is_applied(capsys: pytest.CaptureFixture[str]) -> None:
    """An edited, lower amount is paid; the requested amount is kept."""
    graph = build_graph(InMemorySaver())
    graph.invoke({"request_id": "R-4", "amount": 300}, config("R-4"), version="v2")
    out = graph.invoke(
        Command(resume={"decision": "approve", "amount": 120}), config("R-4"), version="v2"
    )
    assert out.value["status"] == "approved"
    assert out.value["approved_amount"] == 120
    assert out.value["amount"] == 300
    assert "[pay_refund] paying $120 for R-4" in capsys.readouterr().out


def test_invalid_answers_are_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each invalid answer pauses the thread again with an error, until a valid one."""
    # Count check_answer calls: manager_review looks the name up in the module
    # at call time, so patching the module attribute is enough.
    calls: list[Any] = []
    original_check = refunds.check_answer

    def counting_check(answer: Any, requested: int) -> str | None:
        calls.append(answer)
        return original_check(answer, requested)

    monkeypatch.setattr(refunds, "check_answer", counting_check)

    graph = build_graph(InMemorySaver())
    out = graph.invoke({"request_id": "R-5", "amount": 180}, config("R-5"), version="v2")
    question = out.interrupts[0].value["question"]
    assert len(calls) == 0

    out = graph.invoke(Command(resume="yes"), config("R-5"), version="v2")
    assert len(calls) == 1
    assert len(out.interrupts) == 1
    assert out.interrupts[0].value["error"] == DECISION_ERROR
    assert out.interrupts[0].value["question"] == question
    assert "status" not in out.value
    assert graph.get_state(config("R-5")).next == ("manager_review",)

    calls.clear()
    out = graph.invoke(
        Command(resume={"decision": "approve", "amount": 900}), config("R-5"), version="v2"
    )
    assert len(calls) == 1
    assert len(out.interrupts) == 1
    assert out.interrupts[0].value["error"] == "amount must be a whole number from 1 to 180"
    assert "status" not in out.value
    assert graph.get_state(config("R-5")).next == ("manager_review",)

    calls.clear()
    out = graph.invoke(
        Command(resume={"decision": "approve", "amount": 150}), config("R-5"), version="v2"
    )
    assert len(calls) == 1
    assert out.interrupts == ()
    assert out.value["status"] == "approved"
    assert out.value["approved_amount"] == 150
    assert out.value.get("review_error") is None
    assert graph.get_state(config("R-5")).next == ()


def test_small_refund_goes_through_pay_refund() -> None:
    """A small refund skips the manager and is paid in full by policy."""
    graph = build_graph(InMemorySaver())
    out = graph.invoke({"request_id": "R-1", "amount": 40}, config("R-1"), version="v2")
    assert out.interrupts == ()
    assert out.value == {
        "request_id": "R-1",
        "amount": 40,
        "status": "approved",
        "decided_by": "policy",
        "approved_amount": 40,
    }

"""Offline tests for lesson 9.1: the order workflow built with @entrypoint and @task."""

import threading
import uuid

import pytest
from l9_1_entrypoint_and_task.workflow import (
    CheckResult,
    Order,
    check_stock,
    checkpointer,
    decide,
    process_order,
)
from langgraph.func import entrypoint, task

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


def fresh_config(prefix: str) -> dict:
    """A config with a thread_id no other test uses."""
    return {"configurable": {"thread_id": f"{prefix}-{uuid.uuid4()}"}}


def test_same_decisions_as_3_1() -> None:
    """Ada is approved; Bob and Cleo are on hold with 3.1's problem strings."""
    assert process_order.invoke(ADA, fresh_config("test-decisions-ada")) == {
        "order_id": "A-1001",
        "country": "DE",
        "decision": "approved",
        "problems": [],
    }
    assert process_order.invoke(BOB, fresh_config("test-decisions-bob")) == {
        "order_id": "B-1002",
        "country": "UK",
        "decision": "on_hold",
        "problems": [
            "address: no shipping to UK",
            "payment: balance 20.0 < total 60.0",
            "stock: MUG 1>0",
        ],
    }
    assert process_order.invoke(CLEO, fresh_config("test-decisions-cleo")) == {
        "order_id": "C-1003",
        "country": "US",
        "decision": "on_hold",
        "problems": ["address: no shipping to US"],
    }


def test_every_task_reports_an_update() -> None:
    """Each task emits an update under its name; the entrypoint's comes last."""
    chunks = list(process_order.stream(ADA, fresh_config("test-updates"), stream_mode="updates"))
    merged: dict = {}
    for chunk in chunks:
        merged.update(chunk)
    assert sorted(merged) == [
        "check_address",
        "check_payment",
        "check_stock",
        "normalize_address",
        "process_order",
    ]
    assert list(chunks[-1]) == ["process_order"]


def test_task_results_are_checkpointed() -> None:
    """One run writes two checkpoints; the task results hang on the input one."""
    config = fresh_config("test-checkpoints")
    outcome = process_order.invoke(ADA, config)
    checkpoints = list(reversed(list(checkpointer.list(config))))
    assert [(c.metadata["step"], c.metadata["source"]) for c in checkpoints] == [
        (-1, "input"),
        (0, "loop"),
    ]
    returns = [w[2] for w in checkpoints[0].pending_writes or [] if w[1] == "__return__"]
    assert len(returns) == 4
    assert "DE" in returns
    assert sorted(v["check"] for v in returns if isinstance(v, dict)) == [
        "address",
        "payment",
        "stock",
    ]
    snap = process_order.get_state(config)
    assert snap.values == outcome
    assert snap.next == ()


def test_futures_run_concurrently() -> None:
    """Two tasks that wait on each other finish only if both futures exist first."""
    barrier = threading.Barrier(2, timeout=5)

    @task
    def left() -> str:
        """Wait for the other task, then return."""
        barrier.wait()
        return "left"

    @task
    def right() -> str:
        """Wait for the other task, then return."""
        barrier.wait()
        return "right"

    @entrypoint()
    def both(_: int) -> list[str]:
        """Create both futures before waiting on either."""
        a = left()
        b = right()
        return [a.result(), b.result()]

    assert both.invoke(0) == ["left", "right"]


def test_decide_is_a_plain_function() -> None:
    """decide runs outside any entrypoint and ignores the order of the results."""
    bob_results: list[CheckResult] = [
        {"check": "stock", "ok": False, "detail": "MUG 1>0"},
        {"check": "payment", "ok": False, "detail": "balance 20.0 < total 60.0"},
        {"check": "address", "ok": False, "detail": "no shipping to UK"},
    ]
    first = decide(bob_results)
    second = decide(list(reversed(bob_results)))
    assert first == second
    assert first["decision"] == "on_hold"
    assert first["problems"] == [
        "address: no shipping to UK",
        "payment: balance 20.0 < total 60.0",
        "stock: MUG 1>0",
    ]
    # A task needs a running entrypoint or graph to schedule it.
    with pytest.raises(RuntimeError):
        check_stock({"PEN": 1})


def test_thread_id_is_required() -> None:
    """With a checkpointer, invoking without a thread_id is refused."""
    with pytest.raises(ValueError, match="thread_id"):
        process_order.invoke(ADA)

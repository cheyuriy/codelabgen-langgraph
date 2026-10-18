"""Offline tests for lesson 9.2: previous, entrypoint.final, interrupt() and resume."""

from collections import Counter
from collections.abc import Iterator

import pytest
from l9_2_functional_memory_interrupts.workflow import (
    OUTBOX,
    TASK_RUNS,
    Order,
    checkpointer,
    process_order,
)
from langgraph.types import Command

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

BOB_PROBLEMS = [
    "address: no shipping to UK",
    "payment: balance 20.0 < total 60.0",
    "stock: MUG 1>0",
]


@pytest.fixture(autouse=True)
def clean_run_log() -> Iterator[None]:
    """Start every test with an empty task counter and outbox."""
    TASK_RUNS.clear()
    OUTBOX.clear()
    yield


def config_for(name: str) -> dict:
    """A config with a thread_id no other test uses."""
    return {"configurable": {"thread_id": f"test-{name}"}}


def run(order: Order, config: dict, answer: str = "approve") -> dict:
    """Invoke the order and, if it pauses, resume it with the given answer."""
    out = process_order.invoke(order, config, version="v2")
    if out.interrupts:
        out = process_order.invoke(Command(resume=answer), config, version="v2")
    return out.value


def test_approved_order_does_not_pause() -> None:
    """Ada passes every check: no interrupt, no customer notice."""
    out = process_order.invoke(ADA, config_for("approved"), version="v2")
    assert out.interrupts == ()
    assert out.value == {
        "order_id": "A-1001",
        "country": "DE",
        "decision": "approved",
        "problems": [],
    }
    assert OUTBOX == []


def test_on_hold_order_pauses_for_manager() -> None:
    """Bob is on hold: the run pauses with one question and the notice is sent."""
    config = config_for("pause")
    out = process_order.invoke(BOB, config, version="v2")
    assert len(out.interrupts) == 1
    assert out.interrupts[0].value == {
        "order_id": "B-1002",
        "problems": BOB_PROBLEMS,
        "question": "approve or reject?",
    }
    assert process_order.get_state(config).next == ("process_order",)
    assert len(OUTBOX) == 1


def test_resume_reuses_finished_tasks() -> None:
    """On resume the body runs again, but every finished task returns its saved result."""
    config = config_for("resume-bob")
    process_order.invoke(BOB, config, version="v2")
    out = process_order.invoke(Command(resume="reject"), config, version="v2")
    assert out.value["decision"] == "rejected"
    assert TASK_RUNS == Counter(
        {
            "check_stock": 1,
            "check_payment": 1,
            "normalize_address": 1,
            "check_address": 1,
            "notify_customer": 1,
        }
    )
    # The notice task ran once although the body ran twice.
    assert OUTBOX == ["to B-1002: your order is waiting for review"]

    cleo_config = config_for("resume-cleo")
    process_order.invoke(CLEO, cleo_config, version="v2")
    cleo = process_order.invoke(Command(resume="approve"), cleo_config, version="v2")
    assert cleo.value["decision"] == "approved"


def test_previous_and_final_split_value_and_save() -> None:
    """The caller gets outcomes; the checkpoint keeps a per-thread tally for previous."""
    config = config_for("desk")
    values = [
        run(ADA, config),
        run(BOB, config, answer="reject"),
        run(CLEO, config, answer="approve"),
    ]
    assert [v["decision"] for v in values] == ["approved", "rejected", "approved"]
    assert all("orders" not in v for v in values)
    assert process_order.get_state(config).values == {
        "order_id": "C-1003",
        "country": "US",
        "decision": "approved",
        "problems": ["address: no shipping to US"],
    }
    saved = checkpointer.get_tuple(config).checkpoint["channel_values"]["__previous__"]
    assert saved == {"orders": 3, "approved": 2, "rejected": 1}

    # A second thread starts its own tally from previous=None.
    other = config_for("desk-other")
    run(ADA, other)
    saved_other = checkpointer.get_tuple(other).checkpoint["channel_values"]["__previous__"]
    assert saved_other == {"orders": 1, "approved": 1, "rejected": 0}


def test_previous_is_injected(capsys: pytest.CaptureFixture[str]) -> None:
    """A new thread gets previous=None; the next run gets the saved tally."""
    config = config_for("injected")
    run(ADA, config)
    assert "previous=None" in capsys.readouterr().out
    run(ADA, config)
    assert "previous={'orders': 1, 'approved': 1, 'rejected': 0}" in capsys.readouterr().out

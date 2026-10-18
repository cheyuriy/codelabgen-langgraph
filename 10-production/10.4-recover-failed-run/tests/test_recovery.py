"""Offline tests for resuming a failed run from its last checkpoint."""

import asyncio
from typing import Any

import pytest
from l10_4_recover_failed_run.graph import build_graph
from l10_4_recover_failed_run.service import LabelPrinterOffline, ParcelTooHeavy, ShippingApi
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import EmptyInputError

PARIS = {"address": "1 Rue de Rivoli, Paris", "weight_kg": 1.0}
CONFIG: RunnableConfig = {"configurable": {"thread_id": "t"}}


def fail_with_printer_offline(api: ShippingApi, graph: Any, durability: str = "async") -> None:
    """Switch the printer off and run PARIS: book_pickup finishes, print_label fails."""
    api.printer_online = False
    with pytest.raises(LabelPrinterOffline):
        asyncio.run(graph.ainvoke(PARIS, CONFIG, durability=durability))


def test_resume_reruns_only_the_failed_node() -> None:
    """The failed step is saved with book_pickup's write; a resume runs print_label only."""
    api = ShippingApi()
    graph = build_graph(api, checkpointer=InMemorySaver())
    fail_with_printer_offline(api, graph)

    snapshot = graph.get_state(CONFIG)
    assert snapshot.next == ("print_label",)
    # The finished sibling's write is already part of the saved values.
    assert snapshot.values["pickup_id"] == "PU-1"
    assert "label_id" not in snapshot.values
    tasks = {task.name: task for task in snapshot.tasks}
    assert tasks["book_pickup"].error is None
    assert tasks["book_pickup"].result == {"pickup_id": "PU-1"}
    # The saved error is the exception's repr string.
    assert "LabelPrinterOffline" in str(tasks["print_label"].error)

    api.printer_online = True
    result = asyncio.run(graph.ainvoke(None, CONFIG))
    assert result["reply"] == "7.5 EUR to EU"
    assert result["pickup_id"] == "PU-1"
    assert result["label_id"] == "LB-1"
    # Nothing ran twice: one lookup, one rate call, one pickup, one label.
    assert (api.zone_lookups, api.rate_calls, api.pickups_booked, api.labels_printed) == (
        1,
        1,
        1,
        1,
    )
    assert graph.get_state(CONFIG).next == ()


def test_resume_before_the_fix_fails_again() -> None:
    """While the printer is still offline, a resume fails the same way."""
    api = ShippingApi()
    graph = build_graph(api, checkpointer=InMemorySaver())
    fail_with_printer_offline(api, graph)
    with pytest.raises(LabelPrinterOffline):
        asyncio.run(graph.ainvoke(None, CONFIG))
    assert graph.get_state(CONFIG).next == ("print_label",)
    assert api.pickups_booked == 1


@pytest.mark.parametrize(
    ("mode", "before", "after"), [("sync", 4, 6), ("async", 4, 6), ("exit", 1, 2)]
)
def test_every_durability_mode_keeps_the_failed_step(mode: str, before: int, after: int) -> None:
    """On an ordinary exception every mode saves the failed step and its finished writes."""
    api = ShippingApi()
    saver = InMemorySaver()
    graph = build_graph(api, checkpointer=saver)
    fail_with_printer_offline(api, graph, durability=mode)
    assert len(list(saver.list(CONFIG))) == before
    assert graph.get_state(CONFIG).next == ("print_label",)

    api.printer_online = True
    result = asyncio.run(graph.ainvoke(None, CONFIG, durability=mode))
    assert result["pickup_id"] == "PU-1"
    assert api.pickups_booked == 1
    assert len(list(saver.list(CONFIG))) == after


def test_sending_the_input_again_starts_over() -> None:
    """The original input instead of None starts a new run: a second pickup is booked."""
    api = ShippingApi()
    graph = build_graph(api, checkpointer=InMemorySaver())
    fail_with_printer_offline(api, graph)
    api.printer_online = True
    result = asyncio.run(graph.ainvoke(PARIS, CONFIG))
    assert result["pickup_id"] == "PU-2"
    assert api.pickups_booked == 2
    assert api.rate_calls == 2


def test_a_reraised_handler_error_closes_the_thread() -> None:
    """fallback_quote re-raises ParcelTooHeavy: nothing is left to resume."""
    api = ShippingApi()
    graph = build_graph(api, checkpointer=InMemorySaver())
    berlin = {"address": "10 Unter den Linden, Berlin", "weight_kg": 40.0}
    with pytest.raises(ParcelTooHeavy):
        asyncio.run(graph.ainvoke(berlin, CONFIG))
    snapshot = graph.get_state(CONFIG)
    assert snapshot.next == ()
    assert snapshot.tasks == ()
    # The resume runs nothing and returns the saved values.
    result = asyncio.run(graph.ainvoke(None, CONFIG))
    assert result == {"address": "10 Unter den Linden, Berlin", "weight_kg": 40.0, "zone": "EU"}
    assert api.rate_calls == 1


def test_no_checkpoint_nothing_to_resume() -> None:
    """None on a thread without a checkpoint raises EmptyInputError."""
    graph = build_graph(ShippingApi(), checkpointer=InMemorySaver())
    with pytest.raises(EmptyInputError):
        asyncio.run(graph.ainvoke(None, {"configurable": {"thread_id": "nope"}}))

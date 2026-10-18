"""Offline tests for lesson 7.4: the order run read through stream_events v3."""

import pytest
from l7_4_event_streaming.__main__ import ORDER
from l7_4_event_streaming.orders import build_graph
from langchain_core.language_models.chat_model_stream import ChatModelStream
from langgraph.stream import CustomTransformer, GraphRunStream, UpdatesTransformer

# Every stream_events(version="v3") call warns that the API is experimental.
pytestmark = pytest.mark.filterwarnings("ignore:The v3 streaming protocol:DeprecationWarning")

EMAIL = "Order A-1001 shipped. Tracking TRK-A-1001."
SMS = "Shipped: TRK-A-1001"


def test_stream_events_returns_run_stream_and_warns() -> None:
    """stream_events v3 returns a GraphRunStream, warns, and refuses stream_mode."""
    graph = build_graph()
    with pytest.warns(DeprecationWarning, match="experimental"):
        run = graph.stream_events(ORDER, version="v3")
    assert isinstance(run, GraphRunStream)
    assert sorted(run.extensions) == ["lifecycle", "messages", "subgraphs", "values"]
    with pytest.raises(TypeError, match="stream_mode"):
        graph.stream_events(ORDER, version="v3", stream_mode="messages")


def test_values_and_output() -> None:
    """run.values yields each snapshot; run.output is the final state."""
    run = build_graph().stream_events(ORDER, version="v3")
    snapshots = list(run.values)
    assert [s.get("status") for s in snapshots] == [None, "picked", "packed", "shipped", "shipped"]
    assert run.output == snapshots[-1]
    assert run.output == {
        "order_id": "A-1001",
        "items": ["PEN", "NOTEBOOK"],
        "status": "shipped",
        "box": "small",
        "tracking": "TRK-A-1001",
        "email": EMAIL,
        "sms": SMS,
        "note": "Box small handed to carrier.",
    }
    assert run.interrupted is False


def test_messages_one_stream_per_call() -> None:
    """run.messages yields one ChatModelStream per streamed model call."""
    run = build_graph().stream_events(ORDER, version="v3")
    ms = list(run.messages)
    assert len(ms) == 2
    assert all(isinstance(m, ChatModelStream) for m in ms)
    assert [m.node for m in ms] == ["confirm", "confirm"]
    assert [str(m.text) for m in ms] == [EMAIL, SMS]
    assert ms[0].output.text == EMAIL


def test_projections_must_be_subscribed_in_time() -> None:
    """A projection read after the run is empty; interleave reads both in order."""
    graph = build_graph()
    run = graph.stream_events(ORDER, version="v3")
    assert len(list(run.values)) == 5
    assert list(run.messages) == []
    # A projection is a single-consumer cursor: a second iteration is refused.
    with pytest.raises(RuntimeError, match="tee"):
        list(run.values)

    run = graph.stream_events(ORDER, version="v3")
    names = [name for name, _item in run.interleave("values", "messages")]
    assert names == ["values"] * 4 + ["messages"] * 2 + ["values"]
    # interleave() consumed the values projection; reading it again is empty.
    assert list(run.values) == []


def test_opt_in_projections() -> None:
    """updates and custom exist only when their transformers are passed."""
    graph = build_graph()
    run = graph.stream_events(ORDER, version="v3")
    with pytest.raises(AttributeError, match="registered projections"):
        _ = run.updates

    run = graph.stream_events(
        ORDER, version="v3", transformers=[UpdatesTransformer, CustomTransformer]
    )
    assert list(run.custom) == [
        {"node": "pack", "item": "PEN", "done": 1, "total": 2},
        {"node": "pack", "item": "NOTEBOOK", "done": 2, "total": 2},
        {"node": "ship", "label": "TRK-A-1001"},
    ]

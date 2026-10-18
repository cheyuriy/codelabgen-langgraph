"""Offline tests for lesson 7.1: values, updates, a list of modes and v2 parts."""

import warnings

from l7_1_stream_modes.__main__ import ORDER
from l7_1_stream_modes.orders import build_graph
from l7_1_stream_modes.render import describe

FINAL_STATE = {
    "order_id": "A-1001",
    "items": ["PEN", "NOTEBOOK"],
    "status": "shipped",
    "box": "small",
    "tracking": "TRK-A-1001",
}
UPDATES = [
    {"pick": {"status": "picked"}},
    {"pack": {"status": "packed", "box": "small"}},
    {"ship": {"status": "shipped", "tracking": "TRK-A-1001"}},
]


def test_values_streams_input_then_full_state() -> None:
    """values yields the input first, then the whole state after each step."""
    chunks = list(build_graph().stream(ORDER, stream_mode="values"))
    assert len(chunks) == 4
    assert chunks[0] == dict(ORDER)
    assert "status" not in chunks[0]
    assert [c.get("status") for c in chunks] == [None, "picked", "packed", "shipped"]
    assert chunks[-1] == FINAL_STATE


def test_updates_streams_only_node_returns() -> None:
    """updates yields {node: return value}; it is also the default mode."""
    graph = build_graph()
    assert list(graph.stream(ORDER, stream_mode="updates")) == UPDATES
    assert list(graph.stream(ORDER)) == UPDATES

    big = {"order_id": "A-1002", "items": ["PEN", "NOTEBOOK", "STAPLER"]}
    chunks = list(graph.stream(big, stream_mode="updates"))
    assert chunks[1] == {"pack": {"status": "packed", "box": "large"}}


def test_list_of_modes_yields_tuples() -> None:
    """A list of modes in v1 yields (mode, chunk) tuples; list order does not matter."""
    graph = build_graph()
    items = list(graph.stream(ORDER, stream_mode=["values", "updates"]))
    assert all(isinstance(item, tuple) and len(item) == 2 for item in items)
    assert [mode for mode, _ in items] == [
        "values",
        "updates",
        "values",
        "updates",
        "values",
        "updates",
        "values",
    ]
    assert list(graph.stream(ORDER, stream_mode=["updates", "values"])) == items


def _v2_parts() -> list:
    """Stream the order with both modes in v2 format, failing on any warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return list(build_graph().stream(ORDER, stream_mode=["values", "updates"], version="v2"))


def test_v2_parts_have_fixed_shape() -> None:
    """v2 parts are dicts with type, ns, data (and interrupts on values parts)."""
    graph = build_graph()
    parts = _v2_parts()
    assert all(type(p) is dict for p in parts)
    assert all(p["ns"] == () for p in parts)
    for p in parts:
        if p["type"] == "values":
            assert set(p) == {"type", "ns", "data", "interrupts"}
            assert p["interrupts"] == ()
        else:
            assert p["type"] == "updates"
            assert set(p) == {"type", "ns", "data"}

    v1_values = list(graph.stream(ORDER, stream_mode="values"))
    v1_updates = list(graph.stream(ORDER, stream_mode="updates"))
    assert [p["data"] for p in parts if p["type"] == "values"] == v1_values
    assert [p["data"] for p in parts if p["type"] == "updates"] == v1_updates

    single = list(graph.stream(ORDER, stream_mode="updates", version="v2"))
    assert single and all(type(p) is dict and p["type"] == "updates" for p in single)


def test_describe_renders_each_part_type() -> None:
    """describe renders values and updates parts and falls back for other types."""
    lines = [describe(p) for p in _v2_parts()]
    assert lines == [
        "[values]  ns=() status=- interrupts=0",
        "[updates] ns=() pick -> {'status': 'picked'}",
        "[values]  ns=() status=picked interrupts=0",
        "[updates] ns=() pack -> {'status': 'packed', 'box': 'small'}",
        "[values]  ns=() status=packed interrupts=0",
        "[updates] ns=() ship -> {'status': 'shipped', 'tracking': 'TRK-A-1001'}",
        "[values]  ns=() status=shipped interrupts=0",
    ]
    assert (
        describe({"type": "custom", "ns": (), "data": 1}) == "[custom] (not shown in this lesson)"
    )

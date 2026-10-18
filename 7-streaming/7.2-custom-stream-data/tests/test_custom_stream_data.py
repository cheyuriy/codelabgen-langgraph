"""Offline tests for lesson 7.2: custom progress events from get_stream_writer."""

import warnings

import pytest
from l7_2_custom_stream_data.__main__ import ORDER
from l7_2_custom_stream_data.orders import OrderState, build_graph, pack, ship
from l7_2_custom_stream_data.render import describe
from langgraph.runtime import Runtime

PAYLOADS = [
    {"node": "pack", "item": "PEN", "done": 1, "total": 2},
    {"node": "pack", "item": "NOTEBOOK", "done": 2, "total": 2},
    {"node": "ship", "label": "TRK-A-1001"},
]


def test_custom_alone_yields_only_writer_payloads() -> None:
    """stream_mode='custom' yields exactly what the nodes passed to the writer."""
    assert list(build_graph().stream(ORDER, stream_mode="custom")) == PAYLOADS

    three: OrderState = {"order_id": "A-1002", "items": ["PEN", "NOTEBOOK", "STAPLER"]}
    chunks = list(build_graph().stream(three, stream_mode="custom"))
    pack_chunks = [c for c in chunks if c["node"] == "pack"]
    assert len(pack_chunks) == 3
    assert [c["total"] for c in pack_chunks] == [3, 3, 3]
    assert [c["done"] for c in pack_chunks] == [1, 2, 3]


def _v2_parts(modes: list[str]) -> list:
    """Stream ORDER in version='v2' with the given modes, failing on any warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return list(build_graph().stream(ORDER, stream_mode=modes, version="v2"))


def test_custom_and_updates_interleave_in_v2() -> None:
    """Progress parts arrive while pack runs, before pack's updates part."""
    parts = _v2_parts(["updates", "custom"])
    assert [p["type"] for p in parts] == [
        "updates",
        "custom",
        "custom",
        "updates",
        "custom",
        "updates",
    ]
    custom = [p for p in parts if p["type"] == "custom"]
    for part in custom:
        assert isinstance(part, dict)
        assert set(part.keys()) == {"type", "ns", "data"}
        assert part["ns"] == ()
    assert [p["data"] for p in custom] == PAYLOADS
    assert _v2_parts(["custom", "updates"]) == parts


def test_without_custom_the_writer_calls_are_dropped() -> None:
    """Without 'custom' the writer is a no-op: no payloads, no errors."""
    graph = build_graph()
    assert list(graph.stream(ORDER, stream_mode="updates")) == [
        {"pick": {"status": "picked"}},
        {"pack": {"status": "packed", "box": "small"}},
        {"ship": {"status": "shipped", "tracking": "TRK-A-1001"}},
    ]
    assert graph.invoke(ORDER) == {
        "order_id": "A-1001",
        "items": ["PEN", "NOTEBOOK"],
        "status": "shipped",
        "box": "small",
        "tracking": "TRK-A-1001",
    }


def test_nodes_outside_a_run() -> None:
    """get_stream_writer() needs a run; an injected Runtime can be hand-made."""
    with pytest.raises(RuntimeError, match="outside of a runnable context"):
        pack(ORDER)

    written: list = []
    expected = {"status": "shipped", "tracking": "TRK-A-1001"}
    assert ship(ORDER, Runtime(stream_writer=written.append)) == expected
    assert written == [{"node": "ship", "label": "TRK-A-1001"}]
    assert ship(ORDER, Runtime()) == expected


def test_describe_renders_custom_parts_and_keeps_fallback() -> None:
    """describe() prints custom parts and still falls back for other types."""
    lines = [describe(p) for p in _v2_parts(["updates", "custom"])]
    assert lines == [
        "[updates] ns=() pick -> {'status': 'picked'}",
        "[custom]  ns=() {'node': 'pack', 'item': 'PEN', 'done': 1, 'total': 2}",
        "[custom]  ns=() {'node': 'pack', 'item': 'NOTEBOOK', 'done': 2, 'total': 2}",
        "[updates] ns=() pack -> {'status': 'packed', 'box': 'small'}",
        "[custom]  ns=() {'node': 'ship', 'label': 'TRK-A-1001'}",
        "[updates] ns=() ship -> {'status': 'shipped', 'tracking': 'TRK-A-1001'}",
    ]
    assert describe({"type": "tasks", "ns": (), "data": {}}) == "[tasks] (not shown in this lesson)"

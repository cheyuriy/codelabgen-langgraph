"""Offline tests for lesson 7.3: chat-model tokens through stream_mode="messages"."""

import warnings

from l7_3_streaming_llm_tokens.__main__ import ORDER
from l7_3_streaming_llm_tokens.orders import build_graph, confirm
from l7_3_streaming_llm_tokens.render import describe
from langchain_core.messages import AIMessageChunk

EMAIL = "Order A-1001 shipped. Tracking TRK-A-1001."
SMS = "Shipped: TRK-A-1001"
NOTE = "Box small handed to carrier."

SECTION_B = [
    "[updates] ns=() pick -> {'status': 'picked'}",
    "[updates] ns=() pack -> {'status': 'packed', 'box': 'small'}",
    "[updates] ns=() ship -> {'status': 'shipped', 'tracking': 'TRK-A-1001'}",
    "[messages] ns=() confirm 'Order'",
    "[messages] ns=() confirm ' '",
    "[messages] ns=() confirm 'A-1001'",
    "[messages] ns=() confirm ' '",
    "[messages] ns=() confirm 'shipped.'",
    "[messages] ns=() confirm ' '",
    "[messages] ns=() confirm 'Tracking'",
    "[messages] ns=() confirm ' '",
    "[messages] ns=() confirm 'TRK-A-1001.'",
    "[messages] ns=() confirm 'Shipped:'",
    "[messages] ns=() confirm ' '",
    "[messages] ns=() confirm 'TRK-A-1001'",
    "[updates] ns=() confirm -> {'email': 'Order A-1001 shipped. Tracking TRK-A-1001.', "
    "'sms': 'Shipped: TRK-A-1001', 'note': 'Box small handed to carrier.'}",
]


def _messages() -> list:
    """Stream ORDER with stream_mode='messages' (v1) and collect the pairs."""
    return list(build_graph().stream(ORDER, stream_mode="messages"))


def _v2_parts() -> list:
    """Stream ORDER with ['updates', 'messages'] in v2, failing on any warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return list(build_graph().stream(ORDER, stream_mode=["updates", "messages"], version="v2"))


def test_messages_mode_streams_only_tagged_confirm_calls() -> None:
    """Every token comes from confirm; 9 email tokens, then 3 SMS tokens."""
    pairs = _messages()
    assert len(pairs) == 12
    assert all(isinstance(chunk, AIMessageChunk) for chunk, _ in pairs)
    assert all(m["langgraph_node"] == "confirm" for _, m in pairs)
    assert [m.get("tags") for _, m in pairs] == [["email"]] * 9 + [["sms"]] * 3
    assert "".join(c.content for c, m in pairs if m.get("tags") == ["email"]) == EMAIL
    assert "".join(c.content for c, m in pairs if m.get("tags") == ["sms"]) == SMS


def test_tokens_arrive_between_the_updates_in_v2() -> None:
    """The messages parts sit between ship's update and confirm's update."""
    parts = _v2_parts()
    assert [p["type"] for p in parts] == ["updates"] * 3 + ["messages"] * 12 + ["updates"]
    for part in parts:
        if part["type"] == "messages":
            assert set(part.keys()) == {"type", "ns", "data"}
            assert part["ns"] == ()
    assert parts[-1]["data"] == {"confirm": {"email": EMAIL, "sms": SMS, "note": NOTE}}


def test_node_filter_mixes_calls_tag_filter_separates_them() -> None:
    """Filtering by node glues email and SMS; filtering by tag keeps the email."""
    pairs = _messages()
    by_node = "".join(c.content for c, m in pairs if m["langgraph_node"] == "confirm")
    by_tag = "".join(c.content for c, m in pairs if "email" in m.get("tags", []))
    assert by_node == EMAIL + SMS
    assert by_tag == EMAIL


def test_nostream_keeps_note_out_of_stream_not_out_of_state() -> None:
    """The nostream call is missing from the stream but its text is in the state."""
    tags: set[str] = set()
    for _, metadata in _messages():
        tags.update(metadata.get("tags", []))
    assert tags == {"email", "sms"}

    assert build_graph().invoke(ORDER) == {
        "order_id": "A-1001",
        "items": ["PEN", "NOTEBOOK"],
        "status": "shipped",
        "box": "small",
        "tracking": "TRK-A-1001",
        "email": EMAIL,
        "sms": SMS,
        "note": NOTE,
    }
    # Chat models need no run context, so confirm also works outside a graph.
    direct = confirm({**ORDER, "status": "shipped", "box": "small", "tracking": "TRK-A-1001"})
    assert direct == {"email": EMAIL, "sms": SMS, "note": NOTE}


def test_describe_renders_messages_and_keeps_fallback() -> None:
    """describe prints one line per token part and still has the fallback."""
    parts = _v2_parts()
    assert describe(parts[3]) == "[messages] ns=() confirm 'Order'"
    assert [describe(p) for p in parts] == SECTION_B
    assert describe({"type": "tasks", "ns": (), "data": {}}) == "[tasks] (not shown in this lesson)"

"""Offline tests for the lesson 1.1 ticket graph."""

from l1_1_hello_graph.graph import build_graph, clean

URGENT = "The site is DOWN, please fix ASAP!"


def test_clean_returns_partial_update() -> None:
    """clean() returns only its own key, with whitespace collapsed and lowercased."""
    update = clean({"text": "  Hello\n   WORLD  ", "clean_text": "", "priority": ""})
    assert update == {"clean_text": "hello world"}


def test_urgent_ticket_is_high_and_text_kept() -> None:
    """An urgent ticket gets priority high and keeps its original text."""
    result = build_graph().invoke({"text": URGENT})
    assert result["priority"] == "high"
    assert result["text"] == URGENT


def test_plain_ticket_is_normal() -> None:
    """A ticket without urgent keywords gets priority normal."""
    result = build_graph().invoke({"text": "How do I change my   email address?"})
    assert result["priority"] == "normal"
    assert result["clean_text"] == "how do i change my email address?"


def test_stream_updates_per_node() -> None:
    """stream_mode='updates' yields each node's partial update in order."""
    updates = list(build_graph().stream({"text": "  Refund   please "}, stream_mode="updates"))
    assert [next(iter(u)) for u in updates] == ["clean", "tag_priority"]
    assert updates[0] == {"clean": {"clean_text": "refund please"}}
    assert updates[1] == {"tag_priority": {"priority": "high"}}


def test_mermaid_has_edges() -> None:
    """The Mermaid drawing contains the three linear edges."""
    mermaid = build_graph().get_graph().draw_mermaid()
    for edge in ("__start__ --> clean", "clean --> tag_priority", "tag_priority --> __end__"):
        assert edge in mermaid

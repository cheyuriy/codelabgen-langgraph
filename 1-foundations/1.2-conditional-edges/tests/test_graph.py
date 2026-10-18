"""Offline tests for the lesson 1.2 ticket graph with conditional routing."""

import pytest
from l1_2_conditional_edges.graph import build_graph, clean, route_ticket

BILLING_REPLY = "Billing team: we will check your invoice."
TECH_REPLY = "Tech team: we are looking into the problem."
GENERAL_REPLY = "Support team: thanks, we will get back to you."


def test_clean_returns_partial_update() -> None:
    """clean() returns only its own key, with whitespace collapsed and lowercased."""
    update = clean({"text": "  Hello\n   WORLD  ", "clean_text": "", "priority": ""})
    assert update == {"clean_text": "hello world"}


@pytest.mark.parametrize(
    ("ticket", "category", "priority", "reply"),
    [
        ("I was charged twice, please refund me", "billing", "high", BILLING_REPLY),
        ("The app shows an error on login", "tech", "normal", TECH_REPLY),
        ("Do you have a dark mode?", "general", "normal", GENERAL_REPLY),
    ],
)
def test_ticket_routed_to_matching_queue(
    ticket: str, category: str, priority: str, reply: str
) -> None:
    """Each sample ticket gets its category and the matching queue's reply."""
    result = build_graph().invoke({"text": ticket})
    assert result["category"] == category
    assert (result["priority"], result["reply"]) == (priority, reply)


def test_billing_checked_before_tech() -> None:
    """A ticket with both a billing and a tech keyword ends in billing."""
    result = build_graph().invoke({"text": "Payment page shows an error"})
    assert result["category"] == "billing"
    assert result["reply"] == BILLING_REPLY


def test_route_ticket_returns_label() -> None:
    """route_ticket returns a route label, not a state update dict."""
    state = {
        "text": "",
        "clean_text": "",
        "priority": "normal",
        "category": "tech",
        "reply": "",
    }
    assert route_ticket(state) == "tech"


def test_stream_runs_only_one_queue() -> None:
    """stream_mode='updates' shows the linear nodes, classify and one queue node."""
    updates = list(build_graph().stream({"text": "  Refund   please "}, stream_mode="updates"))
    assert [next(iter(u)) for u in updates] == [
        "clean",
        "tag_priority",
        "classify",
        "billing_queue",
    ]
    assert updates[2] == {"classify": {"category": "billing"}}
    assert updates[3] == {"billing_queue": {"reply": BILLING_REPLY}}


def test_mermaid_draws_conditional_edges() -> None:
    """The Mermaid drawing shows classify's dotted, labelled conditional edges."""
    mermaid = build_graph().get_graph().draw_mermaid()
    for edge in (
        "tag_priority --> classify",
        "classify -. &nbsp;billing&nbsp; .-> billing_queue",
        "classify -. &nbsp;tech&nbsp; .-> tech_queue",
        "classify -. &nbsp;general&nbsp; .-> general_queue",
        "billing_queue --> __end__",
    ):
        assert edge in mermaid
    assert "tag_priority --> __end__" not in mermaid

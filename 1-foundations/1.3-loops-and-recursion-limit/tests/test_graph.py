"""Offline tests for the lesson 1.3 ticket graph with a revision loop."""

import pytest
from l1_3_loops_and_recursion_limit.graph import (
    build_graph,
    clean,
    revise,
    route_after_check,
    route_ticket,
)
from langgraph.errors import GraphRecursionError

BILLING_REPLY = (
    "Hi there! Billing team: we will check your invoice. "
    "We are treating this as urgent. Best regards, Support."
)
TECH_REPLY = "Hi there! Tech team: we are looking into the problem. Best regards, Support."
GENERAL_REPLY = "Hi there! Support team: thanks, we will get back to you. Best regards, Support."
BILLING_NORMAL_REPLY = "Hi there! Billing team: we will check your invoice. Best regards, Support."
FIRST_TICKET = "I was charged twice, please refund me"


def test_clean_returns_partial_update() -> None:
    """clean() returns only its own key, with whitespace collapsed and lowercased."""
    update = clean({"text": "  Hello\n   WORLD  ", "clean_text": "", "priority": ""})
    assert update == {"clean_text": "hello world"}


@pytest.mark.parametrize(
    ("ticket", "category", "priority", "reply"),
    [
        (FIRST_TICKET, "billing", "high", BILLING_REPLY),
        ("The app shows an error on login", "tech", "normal", TECH_REPLY),
        ("Do you have a dark mode?", "general", "normal", GENERAL_REPLY),
    ],
)
def test_ticket_routed_and_reply_revised(
    ticket: str, category: str, priority: str, reply: str
) -> None:
    """Each sample ticket gets its category and the fully revised reply."""
    result = build_graph().invoke({"text": ticket})
    assert result["category"] == category
    assert (result["priority"], result["reply"]) == (priority, reply)
    assert result["problems"] == []


def test_billing_checked_before_tech() -> None:
    """A ticket with both a billing and a tech keyword ends in billing."""
    result = build_graph().invoke({"text": "Payment page shows an error"})
    assert result["category"] == "billing"
    assert result["reply"] == BILLING_NORMAL_REPLY


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


def test_revise_fixes_only_first_problem() -> None:
    """revise() fixes one problem per pass and returns only the reply."""
    state = {
        "reply": "Tech team: we are looking into the problem.",
        "problems": ["greeting", "sign_off"],
    }
    assert revise(state) == {"reply": "Hi there! Tech team: we are looking into the problem."}


@pytest.mark.parametrize(
    ("problems", "remaining_steps", "route"),
    [
        ([], 100, "send"),
        (["sign_off"], 3, "revise"),
        (["sign_off"], 2, "send"),
    ],
)
def test_route_after_check(problems: list[str], remaining_steps: int, route: str) -> None:
    """Send when the reply is clean or another round would not fit."""
    state = {"problems": problems, "remaining_steps": remaining_steps}
    assert route_after_check(state) == route


def test_stream_shows_the_loop() -> None:
    """stream_mode='updates' shows one node per super-step, looping until clean."""
    updates = list(build_graph().stream({"text": "  Refund   please "}, stream_mode="updates"))
    assert [next(iter(u)) for u in updates] == [
        "clean",
        "tag_priority",
        "classify",
        "billing_queue",
        "check_reply",
        "revise",
        "check_reply",
        "revise",
        "check_reply",
        "revise",
        "check_reply",
    ]
    assert updates[-1] == {"check_reply": {"problems": []}}


def test_recursion_limit_graceful_stop_and_error() -> None:
    """A small limit stops the loop early; a too-small one raises."""
    graph = build_graph()
    result = graph.invoke({"text": FIRST_TICKET}, {"recursion_limit": 9})
    assert result["reply"] == "Hi there! Billing team: we will check your invoice."
    assert result["problems"] == ["urgent_note", "sign_off"]
    with pytest.raises(GraphRecursionError):
        graph.invoke({"text": FIRST_TICKET}, {"recursion_limit": 5})


def test_mermaid_draws_loop() -> None:
    """The Mermaid drawing shows the queue edges into check_reply and the loop."""
    mermaid = build_graph().get_graph().draw_mermaid()
    for edge in (
        "classify -. &nbsp;billing&nbsp; .-> billing_queue",
        "classify -. &nbsp;tech&nbsp; .-> tech_queue",
        "classify -. &nbsp;general&nbsp; .-> general_queue",
        "billing_queue --> check_reply",
        "revise --> check_reply",
        "check_reply -.-> revise",
        "check_reply -. &nbsp;send&nbsp; .-> __end__",
    ):
        assert edge in mermaid
    assert "billing_queue --> __end__" not in mermaid

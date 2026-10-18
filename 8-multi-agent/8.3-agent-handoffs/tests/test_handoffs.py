"""Offline tests for lesson 8.3: handoffs between the billing and tech teams."""

import pytest
from l8_3_agent_handoffs.__main__ import (
    BILLING_TICKET,
    BILLING_TO_TECH_TICKET,
    GENERAL_TICKET,
    TECH_TICKET,
    TECH_TO_BILLING_TICKET,
    VAGUE_TECH_TICKET,
)
from l8_3_agent_handoffs.billing import build_billing
from l8_3_agent_handoffs.desk import build_desk, classify
from l8_3_agent_handoffs.handoff import hand_off
from l8_3_agent_handoffs.show import brief, label, node_path
from l8_3_agent_handoffs.tech import build_tech
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import ParentCommand
from langgraph.types import Command

BILLING_NOTE = (
    "Billing team: there is no invoice here, this looks technical. Passing you to the tech team."
)
TECH_NOTE = "Tech team: questions about invoices go to billing. Passing you to the billing team."


def thread(thread_id: str) -> dict:
    """A config for one conversation thread."""
    return {"configurable": {"thread_id": thread_id}}


def ask(ticket: str, thread_id: str) -> dict:
    """Invoke a fresh desk with one ticket and return the final state."""
    desk = build_desk(InMemorySaver())
    return desk.invoke({"messages": [HumanMessage(ticket)]}, thread(thread_id))


def test_billing_hands_a_ticket_to_tech() -> None:
    """A tech problem classified as billing ends with a tech reply."""
    result = ask(BILLING_TO_TECH_TICKET, "a")
    assert [(label(m), m.content) for m in result["messages"]] == [
        ("human", BILLING_TO_TECH_TICKET),
        ("billing", BILLING_NOTE),
        ("tech", "Tech team: on your phone, reinstall the app."),
    ]
    assert result["category"] == "tech"
    assert result["handoffs"] == ["billing -> tech"]


def test_tech_hands_a_ticket_to_billing() -> None:
    """An invoice question classified as tech ends with a billing reply."""
    result = ask(TECH_TO_BILLING_TICKET, "b")
    assert [(label(m), m.content) for m in result["messages"]] == [
        ("human", TECH_TO_BILLING_TICKET),
        ("tech", TECH_NOTE),
        ("billing", "Billing team: the refund for INV-2077 is on its way."),
    ]
    assert result["category"] == "billing"
    assert result["handoffs"] == ["tech -> billing"]
    # The classifier still picks the wrong team: the handoff fixed the route.
    assert classify({"messages": [HumanMessage(BILLING_TO_TECH_TICKET)]}) == {"category": "billing"}
    assert classify({"messages": [HumanMessage(TECH_TO_BILLING_TICKET)]}) == {"category": "tech"}


def test_handing_off_node_writes_nothing_in_its_subgraph() -> None:
    """find_invoice emits no update; the root billing update is the handoff's update."""
    desk = build_desk(InMemorySaver())
    parts = list(
        desk.stream(
            {"messages": [HumanMessage(BILLING_TO_TECH_TICKET)]},
            thread("c"),
            stream_mode="updates",
            subgraphs=True,
            version="v2",
        )
    )
    assert [(node_path(p["ns"]), node) for p in parts for node in p["data"]] == [
        ("(root)", "classify"),
        ("(root)", "billing"),
        ("tech", "identify_device"),
        ("tech", "suggest_fix"),
        ("(root)", "tech"),
    ]
    root_billing = next(
        p["data"]["billing"] for p in parts if not p["ns"] and "billing" in p["data"]
    )
    assert brief(root_billing) == {
        "messages": ["billing"],
        "category": "tech",
        "handoffs": ["billing -> tech"],
    }


def test_reducer_keeps_every_handoff_on_a_thread() -> None:
    """operator.add keeps both handoffs; tickets without a handoff leave the log empty."""
    desk = build_desk(InMemorySaver())
    config = thread("d")
    desk.invoke({"messages": [HumanMessage(BILLING_TO_TECH_TICKET)]}, config)
    desk.invoke({"messages": [HumanMessage(TECH_TO_BILLING_TICKET)]}, config)
    values = desk.get_state(config).values
    assert values["handoffs"] == ["billing -> tech", "tech -> billing"]
    assert len(values["messages"]) == 6

    expected = {
        BILLING_TICKET: "Billing team: the refund for INV-1042 is on its way.",
        TECH_TICKET: "Tech team: on your laptop, restart it and install the latest updates.",
        GENERAL_TICKET: "Support team: thanks, we will get back to you.",
    }
    for index, (ticket, reply) in enumerate(expected.items()):
        result = ask(ticket, f"plain-{index}")
        assert result["handoffs"] == []
        assert result["messages"][-1].content == reply


def test_command_parent_needs_a_parent() -> None:
    """hand_off builds a Command.PARENT; a team on its own raises ParentCommand."""
    command = hand_off("billing", "tech", "x")
    assert command.graph == Command.PARENT
    assert command.goto == "tech"
    assert command.update["category"] == "tech"
    assert command.update["handoffs"] == ["billing -> tech"]

    with pytest.raises(ParentCommand) as billing_exc:
        build_billing().invoke({"messages": [HumanMessage(BILLING_TO_TECH_TICKET)]})
    assert billing_exc.value.args[0].goto == "tech"
    assert sorted(billing_exc.value.args[0].update) == ["category", "handoffs", "messages"]

    with pytest.raises(ParentCommand) as tech_exc:
        build_tech().invoke({"problem": TECH_TO_BILLING_TICKET})
    assert tech_exc.value.args[0].goto == "billing"
    assert sorted(tech_exc.value.args[0].update) == ["category", "handoffs", "messages"]


def test_the_8_2_pause_still_works() -> None:
    """A vague tech ticket still pauses inside tech and resumes with the answer."""
    desk = build_desk(InMemorySaver())
    config = thread("e")
    out = desk.invoke({"messages": [HumanMessage(VAGUE_TECH_TICKET)]}, config, version="v2")
    assert out.interrupts[0].value == "Which device are you using: laptop, phone or router?"
    out = desk.invoke(Command(resume="phone"), config, version="v2")
    assert out.value["messages"][-1].content == "Tech team: on your phone, reinstall the app."
    assert out.value["handoffs"] == []

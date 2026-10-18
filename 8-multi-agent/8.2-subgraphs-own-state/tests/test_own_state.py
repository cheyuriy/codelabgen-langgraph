"""Offline tests for lesson 8.2: a subgraph with its own state, called inside a node."""

from l8_2_subgraphs_own_state.__main__ import (
    BILLING_TICKET,
    GENERAL_TICKET,
    TECH_TICKET,
    VAGUE_TECH_TICKET,
)
from l8_2_subgraphs_own_state.desk import build_desk, classify
from l8_2_subgraphs_own_state.show import brief, label, node_path
from l8_2_subgraphs_own_state.tech import build_tech
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, StateSnapshot

QUESTION = "Which device are you using: laptop, phone or router?"


def stream_updates(desk, ticket: str, thread_id: str) -> list[dict]:
    """Stream one ticket with subgraph updates and return all parts."""
    return list(
        desk.stream(
            {"messages": [HumanMessage(ticket)]},
            {"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
            subgraphs=True,
            version="v2",
        )
    )


def test_tech_node_maps_state_in_and_out() -> None:
    """Only the reply message reaches the desk; TechState keys stay inside."""
    desk = build_desk(InMemorySaver())
    result = desk.invoke(
        {"messages": [HumanMessage(TECH_TICKET)]}, {"configurable": {"thread_id": "t"}}
    )
    assert [(label(m), m.content) for m in result["messages"]] == [
        ("human", TECH_TICKET),
        ("tech", "Tech team: on your laptop, restart it and install the latest updates."),
    ]
    assert result["category"] == "tech"
    assert sorted(result) == ["category", "messages"]


def test_tech_graph_works_on_its_own() -> None:
    """The tech graph runs with its own schema, and classify routes all tickets."""
    assert build_tech().invoke({"problem": "My router is down."}) == {
        "problem": "My router is down.",
        "device": "router",
        "fix": "unplug it for 30 seconds",
    }
    tickets = [BILLING_TICKET, TECH_TICKET, VAGUE_TECH_TICKET, GENERAL_TICKET]
    categories = [classify({"messages": [HumanMessage(t)]})["category"] for t in tickets]
    assert categories == ["billing", "tech", "tech", "general"]


def test_both_ways_stream_but_write_different_updates() -> None:
    """Both subgraphs stream inner steps; the root updates differ."""
    desk = build_desk(InMemorySaver())
    assert [name for name, _ in desk.get_subgraphs()] == ["billing", "tech"]

    parts = stream_updates(desk, TECH_TICKET, "tech")
    assert [(node_path(p["ns"]), node) for p in parts for node in p["data"]] == [
        ("(root)", "classify"),
        ("tech", "identify_device"),
        ("tech", "suggest_fix"),
        ("(root)", "tech"),
    ]
    assert all(p["ns"][0].startswith("tech:") for p in parts if p["ns"])
    assert brief(parts[-1]["data"]["tech"]) == {"messages": ["tech"]}

    parts = stream_updates(desk, BILLING_TICKET, "billing")
    assert parts[-1]["ns"] == ()
    assert brief(parts[-1]["data"]["billing"]) == {"messages": ["human", "billing"]}


def test_paused_subgraph_state_is_readable() -> None:
    """While paused, get_state(subgraphs=True) loads the subgraph's own snapshot."""
    desk = build_desk(InMemorySaver())
    config = {"configurable": {"thread_id": "p"}}
    out = desk.invoke({"messages": [HumanMessage(VAGUE_TECH_TICKET)]}, config, version="v2")
    assert out.interrupts[0].value == QUESTION

    parent = desk.get_state(config)
    assert parent.next == ("tech",)
    pointer = parent.tasks[0].state
    assert isinstance(pointer, dict)
    assert sorted(pointer["configurable"]) == ["checkpoint_ns", "thread_id"]
    assert node_path(pointer["configurable"]["checkpoint_ns"].split("|")) == "tech"

    tech_state = desk.get_state(config, subgraphs=True).tasks[0].state
    assert isinstance(tech_state, StateSnapshot)
    assert tech_state.values == {"problem": VAGUE_TECH_TICKET}
    assert tech_state.next == ("identify_device",)


def test_resume_finishes_ticket_and_leaves_nothing_pending() -> None:
    """Resume continues the subgraph in its own history and completes the reply."""
    saver = InMemorySaver()
    desk = build_desk(saver)
    config = {"configurable": {"thread_id": "p"}}
    desk.invoke({"messages": [HumanMessage(VAGUE_TECH_TICKET)]}, config, version="v2")

    out = desk.invoke(Command(resume="phone"), config, version="v2")
    assert out.interrupts == ()
    last = out.value["messages"][-1]
    assert (label(last), last.content) == ("tech", "Tech team: on your phone, reinstall the app.")
    assert desk.get_state(config, subgraphs=True).tasks == ()

    namespaces = {c.config["configurable"]["checkpoint_ns"] for c in saver.list(config)}
    assert len(namespaces) == 2
    assert "" in namespaces
    assert {node_path(ns.split("|")) for ns in namespaces} == {"(root)", "tech"}

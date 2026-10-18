"""Offline tests for lesson 8.1: subgraphs with shared state."""

from collections import Counter

from l8_1_subgraphs_shared_state.__main__ import BILLING_TICKET, GENERAL_TICKET
from l8_1_subgraphs_shared_state.desk import build_desk
from l8_1_subgraphs_shared_state.show import brief, label, node_path
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

BILLING_REPLY = "Billing team: the refund for INV-1042 is on its way."


def _config(thread_id: str) -> dict:
    """A config that selects one thread."""
    return {"configurable": {"thread_id": thread_id}}


def test_billing_ticket_only_shared_keys_come_back() -> None:
    """The subgraph answers; invoice_id stays inside, category stays put."""
    desk = build_desk(InMemorySaver())
    result = desk.invoke({"messages": [HumanMessage(BILLING_TICKET)]}, _config("t"))
    assert [(label(m), m.content) for m in result["messages"]] == [
        ("human", BILLING_TICKET),
        ("billing", BILLING_REPLY),
    ]
    assert result["category"] == "billing"
    assert "invoice_id" not in result

    other = desk.invoke({"messages": [HumanMessage("I want a refund")]}, _config("u"))
    assert other["messages"][-1].content == ("Billing team: the refund for unknown is on its way.")


def test_general_ticket_never_enters_subgraph() -> None:
    """A general ticket only produces root updates: classify and general."""
    desk = build_desk(None)
    parts = list(
        desk.stream(
            {"messages": [HumanMessage(GENERAL_TICKET)]},
            stream_mode="updates",
            subgraphs=True,
            version="v2",
        )
    )
    assert len(parts) == 2
    assert all(p["ns"] == () for p in parts)
    assert [node for p in parts for node in p["data"]] == ["classify", "general"]
    last = parts[-1]["data"]["general"]["messages"][-1]
    assert label(last) == "general"
    assert last.content == "Support team: thanks, we will get back to you."


def test_stream_with_subgraphs_shows_both_levels() -> None:
    """subgraphs=True adds namespaced subgraph updates; the merge keeps 2 messages."""
    desk = build_desk(InMemorySaver())
    config = _config("s")
    parts = list(
        desk.stream(
            {"messages": [HumanMessage(BILLING_TICKET)]},
            config,
            stream_mode="updates",
            subgraphs=True,
            version="v2",
        )
    )
    seen = [(node_path(p["ns"]), node) for p in parts for node in p["data"]]
    assert seen == [
        ("(root)", "classify"),
        ("billing", "find_invoice"),
        ("billing", "draft_reply"),
        ("(root)", "billing"),
    ]
    for p in parts:
        if node_path(p["ns"]) == "billing":
            assert len(p["ns"]) == 1
            assert p["ns"][0].startswith("billing:")
    root_billing = parts[-1]["data"]["billing"]
    assert brief(root_billing) == {"messages": ["human", "billing"]}
    assert len(desk.get_state(config).values["messages"]) == 2

    plain = desk.stream(
        {"messages": [HumanMessage(BILLING_TICKET)]},
        _config("s2"),
        stream_mode="updates",
        version="v2",
    )
    assert [(node_path(p["ns"]), node) for p in plain for node in p["data"]] == [
        ("(root)", "classify"),
        ("(root)", "billing"),
    ]


def test_xray_draws_subgraph_nodes() -> None:
    """get_graph(xray=True) expands the billing node into its own nodes."""
    desk = build_desk(None)
    nodes = list(desk.get_graph().nodes)
    assert "billing" in nodes
    assert "billing:find_invoice" not in nodes
    assert set(desk.get_graph(xray=True).nodes) == {
        "__start__",
        "classify",
        "general",
        "__end__",
        "billing:find_invoice",
        "billing:draft_reply",
    }
    assert "subgraph billing" in desk.get_graph(xray=True).draw_mermaid()
    assert [name for name, _ in desk.get_subgraphs()] == ["billing"]


def test_parent_checkpointer_saves_subgraph_checkpoints() -> None:
    """The subgraph has no saver, yet its checkpoints land in the parent's."""
    saver = InMemorySaver()
    desk = build_desk(saver)
    config = _config("ticket-1")
    assert dict(desk.get_subgraphs())["billing"].checkpointer is None

    def counts() -> Counter:
        return Counter(
            node_path(t.config["configurable"]["checkpoint_ns"].split("|"))
            for t in saver.list(config)
        )

    desk.invoke({"messages": [HumanMessage(BILLING_TICKET)]}, config)
    assert counts() == {"(root)": 4, "billing": 4}

    desk.invoke({"messages": [HumanMessage(BILLING_TICKET)]}, config)
    assert counts() == {"(root)": 8, "billing": 8}
    namespaces = {
        t.config["configurable"]["checkpoint_ns"]
        for t in saver.list(config)
        if t.config["configurable"]["checkpoint_ns"]
    }
    # Compare only how many there are, never the raw ids.
    assert len(namespaces) == 2


def test_show_helpers() -> None:
    """node_path keeps node names only; label prefers the message name."""
    assert node_path(()) == "(root)"
    assert node_path(("billing:1234",)) == "billing"
    assert node_path(("desk:1", "billing:2")) == "desk/billing"
    assert node_path("".split("|")) == "(root)"
    assert label(HumanMessage("x")) == "human"
    assert label(AIMessage("y", name="billing")) == "billing"

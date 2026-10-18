"""Offline tests for lesson 4.1: MessagesState, add_messages and the scripted model."""

import operator

import pytest
from l4_1_messages_state.chatbot import build_graph, make_model
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph, add_messages


def make_history() -> list:
    """Return a fresh two-message history with fixed ids."""
    return [HumanMessage("What is 2 + 3?", id="q1"), AIMessage("2 + 3 is 6.", id="a1")]


def test_two_turn_chat() -> None:
    """Turn 1 appends the reply; turn 2 keeps the old ids and appends two messages."""
    graph = build_graph(make_model(["2 + 3 is 5.", "5 times 4 is 20."]))
    result = graph.invoke({"messages": [("user", "What is 2 + 3?")]})
    msgs = result["messages"]
    assert [m.type for m in msgs] == ["human", "ai"]
    assert [m.content for m in msgs] == ["What is 2 + 3?", "2 + 3 is 5."]
    assert all(m.id for m in msgs)
    assert not any(isinstance(m, SystemMessage) for m in msgs)

    result2 = graph.invoke({"messages": msgs + [("user", "And times 4?")]})
    msgs2 = result2["messages"]
    assert len(msgs2) == 4
    assert msgs2[-1].content == "5 times 4 is 20."
    assert [m.id for m in msgs2[:2]] == [m.id for m in msgs]


def test_add_messages_direct() -> None:
    """add_messages appends new ids, replaces known ids, removes by id; operator.add duplicates."""
    history = make_history()

    appended = add_messages(history, [HumanMessage("And times 4?", id="q2")])
    assert [m.id for m in appended] == ["q1", "a1", "q2"]

    replaced = add_messages(history, [AIMessage("2 + 3 is 5.", id="a1")])
    assert len(replaced) == 2
    assert replaced[1].id == "a1"
    assert replaced[1].content == "2 + 3 is 5."

    removed = add_messages(history, [RemoveMessage(id="q1")])
    assert [m.id for m in removed] == ["a1"]

    concatenated = operator.add(history, [AIMessage("2 + 3 is 5.", id="a1")])
    assert len(concatenated) == 3
    assert [m.id for m in concatenated].count("a1") == 2

    assert history == make_history()


def test_remove_unknown_id_raises() -> None:
    """Removing an id that is not in the history is an error."""
    with pytest.raises(ValueError, match="doesn't exist"):
        add_messages(make_history(), [RemoveMessage(id="nope")])


def test_add_messages_inside_graph() -> None:
    """The reducer merges by id inside a graph too: re-returned messages replace, not duplicate."""

    def return_full_state(state: MessagesState) -> dict:
        """Return the whole history plus a reply (the common pitfall)."""
        return {"messages": state["messages"] + [AIMessage("ok")]}

    builder = StateGraph(MessagesState)
    builder.add_node("node", return_full_state)
    builder.add_edge(START, "node")
    builder.add_edge("node", END)
    result = builder.compile().invoke({"messages": [("user", "hi")]})
    assert len(result["messages"]) == 2

    def remove_first(state: MessagesState) -> dict:
        """Delete the first message by id."""
        return {"messages": [RemoveMessage(id=state["messages"][0].id)]}

    builder2 = StateGraph(MessagesState)
    builder2.add_node("node", remove_first)
    builder2.add_edge(START, "node")
    builder2.add_edge("node", END)
    result2 = builder2.compile().invoke({"messages": make_history()})
    assert [m.id for m in result2["messages"]] == ["a1"]


def test_script_consumed_once() -> None:
    """A third invoke after a two-reply script fails.

    Pinned 1.2.16 behaviour: the iterator's StopIteration surfaces as
    RuntimeError "generator raised StopIteration".
    """
    graph = build_graph(make_model(["2 + 3 is 5.", "5 times 4 is 20."]))
    graph.invoke({"messages": [("user", "a")]})
    graph.invoke({"messages": [("user", "b")]})
    with pytest.raises(RuntimeError):
        graph.invoke({"messages": [("user", "c")]})

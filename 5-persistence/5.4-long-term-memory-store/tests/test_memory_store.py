"""Offline tests for lesson 5.4: per-thread messages, per-user store memory."""

import pytest
from l5_4_long_term_memory_store.assistant import UserContext, build_graph
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.memory import InMemoryStore


def say(graph: CompiledStateGraph, thread_id: str, user_id: str, text: str) -> dict:
    """Invoke the graph with one message and return the final state."""
    return graph.invoke(
        {"messages": [HumanMessage(text)]},
        {"configurable": {"thread_id": thread_id}},
        context=UserContext(user_id=user_id),
    )


def reply(graph: CompiledStateGraph, thread_id: str, user_id: str, text: str) -> str:
    """Invoke the graph and return the assistant's reply text."""
    return say(graph, thread_id, user_id, text)["messages"][-1].content


def test_memory_crosses_threads() -> None:
    """Genres saved on one thread are used on another; messages are not."""
    graph = build_graph(InMemorySaver(), InMemoryStore())
    say(graph, "t1", "ada", "I love sci-fi and mystery.")
    result = say(graph, "t2", "ada", "Recommend something.")
    assert result["messages"][-1].content == (
        "Try: The Hound of the Baskervilles (mystery); Dune (sci-fi)."
    )
    assert len(result["messages"]) == 2
    t1 = graph.get_state({"configurable": {"thread_id": "t1"}})
    assert len(t1.values["messages"]) == 2


def test_namespaces_isolate_users() -> None:
    """Bob does not see Ada's genres, and each user gets one namespace."""
    store = InMemoryStore()
    graph = build_graph(InMemorySaver(), store)
    say(graph, "a1", "ada", "I love sci-fi and mystery.")
    assert reply(graph, "b1", "bob", "Recommend something.") == (
        "Tell me a genre you like and I will pick a book."
    )
    assert store.search(("bob", "genres")) == []
    say(graph, "b1", "bob", "I love fantasy.")
    assert store.list_namespaces() == [("ada", "genres"), ("bob", "genres")]
    assert reply(graph, "a2", "ada", "Recommend something.") == (
        "Try: The Hound of the Baskervilles (mystery); Dune (sci-fi)."
    )


def test_put_is_an_upsert_and_get_sees_it() -> None:
    """A second put on the same key replaces the value; filter drops avoided genres."""
    store = InMemoryStore()
    graph = build_graph(InMemorySaver(), store)
    say(graph, "t", "ada", "I love sci-fi and mystery.")
    assert reply(graph, "t", "ada", "Please skip mystery for now.") == (
        "Noted: mystery (like -> avoid)."
    )
    item = store.get(("ada", "genres"), "mystery")
    assert item is not None
    assert item.value == {"genre": "mystery", "stance": "avoid"}
    assert len(store.search(("ada", "genres"))) == 2
    assert reply(graph, "t", "ada", "I love sci-fi.") == "Noted: sci-fi (already like)."
    assert reply(graph, "t", "ada", "Recommend something.") == "Try: Dune (sci-fi)."


def test_caller_and_nodes_share_one_store() -> None:
    """Values put by the caller are read by the nodes, from any graph on that store."""
    store = InMemoryStore()
    store.put(("bob", "genres"), "history", {"genre": "history", "stance": "like"})
    graph = build_graph(InMemorySaver(), store)
    assert reply(graph, "b1", "bob", "Recommend something.") == "Try: SPQR (history)."
    other = build_graph(InMemorySaver(), store)
    assert reply(other, "b2", "bob", "Recommend something.") == "Try: SPQR (history)."


def test_misuse_errors() -> None:
    """No store means runtime.store is None; no context means no user id."""
    no_store = build_graph(InMemorySaver(), None)
    with pytest.raises(AttributeError, match="'get'"):
        say(no_store, "t", "ada", "I love sci-fi.")

    graph = build_graph(InMemorySaver(), InMemoryStore())
    with pytest.raises(AttributeError, match="user_id"):
        graph.invoke(
            {"messages": [HumanMessage("I love sci-fi.")]},
            {"configurable": {"thread_id": "t"}},
        )

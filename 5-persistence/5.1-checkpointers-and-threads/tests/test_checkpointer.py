"""Offline tests for lesson 5.1: checkpointers, threads and the StateSnapshot."""

import pytest
from l5_1_checkpointers_and_threads.chatbot import build_graph, make_model, tool_call
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

CHAT1: RunnableConfig = {"configurable": {"thread_id": "chat-1"}}
CHAT2: RunnableConfig = {"configurable": {"thread_id": "chat-2"}}
QUESTION = "What is 3 + 4?"
FOLLOW_UP = "Now multiply that by 2."


def two_turn_script() -> list[AIMessage]:
    """Return fresh replies for both chat-1 turns (the fake mutates scripted messages)."""
    return [
        tool_call("add", "call_1", a=3, b=4),
        AIMessage("3 + 4 is 7."),
        tool_call("multiply", "call_2", a=7, b=2),
        AIMessage("7 * 2 is 14."),
    ]


def run_two_turns(extra: list[AIMessage] | None = None) -> tuple[CompiledStateGraph, InMemorySaver]:
    """Build a checkpointed graph and run both chat-1 turns on it."""
    checkpointer = InMemorySaver()
    graph = build_graph(make_model(two_turn_script() + (extra or [])), checkpointer)
    graph.invoke({"messages": [HumanMessage(QUESTION)]}, CHAT1)
    graph.invoke({"messages": [HumanMessage(FOLLOW_UP)]}, CHAT1)
    return graph, checkpointer


def test_memory_within_a_thread() -> None:
    """The second invoke sends one message but sees the whole first turn."""
    graph = build_graph(make_model(two_turn_script()), InMemorySaver())
    first = graph.invoke({"messages": [HumanMessage(QUESTION)]}, CHAT1)
    assert len(first["messages"]) == 4

    second = graph.invoke({"messages": [HumanMessage(FOLLOW_UP)]}, CHAT1)
    messages = second["messages"]
    assert [m.type for m in messages] == ["human", "ai", "tool", "ai", "human", "ai", "tool", "ai"]
    assert messages[0].content == QUESTION
    assert messages[-1].content == "7 * 2 is 14."

    saved = graph.get_state(CHAT1).values["messages"]
    assert [m.content for m in saved] == [m.content for m in messages]


def test_threads_are_separate() -> None:
    """A new thread_id starts empty; other threads are untouched."""
    reply = AIMessage("Multiply what? This conversation has no earlier result.")
    graph, _ = run_two_turns(extra=[reply])

    result = graph.invoke({"messages": [HumanMessage(FOLLOW_UP)]}, CHAT2)
    assert len(result["messages"]) == 2
    assert len(graph.get_state(CHAT1).values["messages"]) == 8

    unused = graph.get_state({"configurable": {"thread_id": "chat-3"}})
    assert unused.values == {}
    assert unused.next == ()


def test_when_checkpoints_are_written() -> None:
    """One input checkpoint per invoke, then one loop checkpoint per super-step."""
    checkpointer = InMemorySaver()
    graph = build_graph(make_model(two_turn_script()), checkpointer)

    events = list(
        graph.stream({"messages": [HumanMessage(QUESTION)]}, CHAT1, stream_mode="checkpoints")
    )
    assert [(e["metadata"]["step"], e["metadata"]["source"], e["next"]) for e in events] == [
        (-1, "input", ["__start__"]),
        (0, "loop", ["call_model"]),
        (1, "loop", ["tools"]),
        (2, "loop", ["call_model"]),
        (3, "loop", []),
    ]
    assert [len(e["values"].get("messages", [])) for e in events] == [0, 1, 2, 3, 4]

    graph.invoke({"messages": [HumanMessage(FOLLOW_UP)]}, CHAT1)
    saved = list(checkpointer.list(CHAT1))
    assert len(saved) == 10
    # checkpointer.list returns newest first; reverse it into the order written.
    pairs = [(c.metadata["step"], c.metadata["source"]) for c in reversed(saved)]
    assert pairs[5:] == [(4, "input"), (5, "loop"), (6, "loop"), (7, "loop"), (8, "loop")]


def test_state_snapshot_after_turn_two() -> None:
    """get_state returns the thread's latest checkpoint as a StateSnapshot."""
    graph, checkpointer = run_two_turns()
    snap = graph.get_state(CHAT1)

    assert isinstance(snap, StateSnapshot)
    assert snap.next == ()
    assert snap.tasks == ()
    conf = snap.config["configurable"]
    assert conf["thread_id"] == "chat-1"
    assert conf["checkpoint_ns"] == ""
    latest = checkpointer.get_tuple(CHAT1)
    assert latest is not None
    assert conf["checkpoint_id"] == latest.config["configurable"]["checkpoint_id"]
    assert snap.metadata is not None
    assert snap.metadata["step"] == 8
    assert snap.metadata["source"] == "loop"
    assert snap.parent_config is not None


def test_failed_run_keeps_its_progress() -> None:
    """A crash in the tools node leaves the checkpoint written after call_model."""
    graph = build_graph(make_model([tool_call("divide", "call_1", a=1, b=0)]), InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "broken"}}

    with pytest.raises(ZeroDivisionError):
        graph.invoke({"messages": [HumanMessage("What is 1 / 0?")]}, config)

    snap = graph.get_state(config)
    assert len(snap.values["messages"]) == 2
    assert snap.next == ("tools",)
    assert snap.metadata is not None
    assert snap.metadata["step"] == 1
    assert snap.tasks[0].name == "tools"
    # The error went through the checkpointer's serializer, which stores an
    # exception as its repr (langgraph-checkpoint 4.3.0, serde/jsonplus.py).
    assert snap.tasks[0].error == "ZeroDivisionError('division by zero')"


def test_misuse_errors() -> None:
    """A checkpointed graph needs a thread_id; get_state needs a checkpointer."""
    graph = build_graph(make_model([AIMessage("hi")]), InMemorySaver())
    with pytest.raises(ValueError, match="thread_id"):
        graph.invoke({"messages": [HumanMessage(QUESTION)]})

    no_memory = build_graph(make_model([AIMessage("hi")]), None)
    with pytest.raises(ValueError, match="No checkpointer set"):
        no_memory.get_state(CHAT1)

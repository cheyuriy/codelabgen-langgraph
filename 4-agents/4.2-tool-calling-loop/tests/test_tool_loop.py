"""Offline tests for the hand-built tool-calling loop."""

import itertools
from collections.abc import Iterator

import pytest
from l4_2_tool_calling_loop.chatbot import (
    build_graph,
    make_model,
    tool_call,
    unanswered_tool_calls,
)
from l4_2_tool_calling_loop.tools import TOOLS, add, divide
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import tools_condition

QUESTION = "What is (3 + 4) * 2 / 7?"


def loop_script() -> list[AIMessage]:
    """Section (a)'s script, built fresh each time (the fake mutates the messages)."""
    return [
        tool_call("add", "call_1", a=3, b=4),
        tool_call("multiply", "call_2", a=7, b=2),
        tool_call("divide", "call_3", a=14, b=7),
        AIMessage("(3 + 4) * 2 / 7 is 2.0."),
    ]


def parallel_script() -> list[AIMessage]:
    """Section (b)'s script: one reply with two tool calls, then the answer."""
    return [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "add", "args": {"a": 3, "b": 4}, "id": "call_a"},
                {"name": "multiply", "args": {"a": 5, "b": 6}, "id": "call_b"},
            ],
        ),
        AIMessage("3 + 4 is 7 and 5 * 6 is 30."),
    ]


def test_full_loop() -> None:
    """The loop runs three tools and ends with the model's plain answer."""
    graph = build_graph(make_model(loop_script()))
    result = graph.invoke({"messages": [HumanMessage(QUESTION)]}, {"recursion_limit": 10})
    messages = result["messages"]
    assert [m.type for m in messages] == ["human", "ai", "tool", "ai", "tool", "ai", "tool", "ai"]
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    assert [m.content for m in tool_msgs] == ["7", "14", "2.0"]
    assert [m.tool_call_id for m in tool_msgs] == ["call_1", "call_2", "call_3"]
    assert [m.name for m in tool_msgs] == ["add", "multiply", "divide"]
    assert messages[-1].content == "(3 + 4) * 2 / 7 is 2.0."
    assert not messages[-1].tool_calls


def test_loop_shape_and_recursion_limit() -> None:
    """The stream alternates call_model / tools; 7 steps need recursion_limit 8."""
    graph = build_graph(make_model(loop_script()))
    nodes = [
        node
        for update in graph.stream(
            {"messages": [HumanMessage(QUESTION)]},
            {"recursion_limit": 10},
            stream_mode="updates",
        )
        for node in update
    ]
    assert nodes == [
        "call_model",
        "tools",
        "call_model",
        "tools",
        "call_model",
        "tools",
        "call_model",
    ]

    with pytest.raises(GraphRecursionError):
        build_graph(make_model(loop_script())).invoke(
            {"messages": [HumanMessage(QUESTION)]}, {"recursion_limit": 7}
        )
    result = build_graph(make_model(loop_script())).invoke(
        {"messages": [HumanMessage(QUESTION)]}, {"recursion_limit": 8}
    )
    assert result["messages"][-1].content == "(3 + 4) * 2 / 7 is 2.0."


def test_tools_and_router() -> None:
    """Tools are runnables; tools_condition routes on the last message's tool calls."""
    assert add.invoke({"a": 3, "b": 4}) == 7
    assert divide.invoke({"a": 14, "b": 7}) == 2.0
    assert [t.name for t in TOOLS] == ["add", "multiply", "divide"]
    assert tools_condition({"messages": [tool_call("add", "c1", a=1, b=2)]}) == "tools"
    assert tools_condition({"messages": [AIMessage("done")]}) == "__end__"


def test_pairing() -> None:
    """ToolMessages answer the calls in order; unanswered_tool_calls finds gaps."""
    graph = build_graph(make_model(parallel_script()))
    result = graph.invoke(
        {"messages": [HumanMessage("What are 3 + 4 and 5 * 6?")]}, {"recursion_limit": 10}
    )
    messages = result["messages"]
    asking = [m for m in messages if isinstance(m, AIMessage) and m.tool_calls]
    assert len(asking) == 1
    assert len(asking[0].tool_calls) == 2
    idx = messages.index(asking[0])
    tool_msgs = messages[idx + 1 : idx + 3]
    assert all(isinstance(m, ToolMessage) for m in tool_msgs)
    assert [m.tool_call_id for m in tool_msgs] == ["call_a", "call_b"]
    assert [m.content for m in tool_msgs] == ["7", "30"]

    assert unanswered_tool_calls(messages) == []
    broken = [
        m for m in messages if not (isinstance(m, ToolMessage) and m.tool_call_id == "call_b")
    ]
    assert unanswered_tool_calls(broken) == ["call_b"]
    assert unanswered_tool_calls([tool_call("add", "x", a=1, b=2)]) == ["x"]


def test_tool_errors_default_handling() -> None:
    """A tool exception propagates; an unknown tool becomes an error ToolMessage."""
    graph = build_graph(make_model([tool_call("divide", "call_1", a=1, b=0)]))
    with pytest.raises(ZeroDivisionError):
        graph.invoke({"messages": [HumanMessage("1 / 0?")]}, {"recursion_limit": 10})

    graph = build_graph(
        make_model(
            [
                tool_call("subtract", "call_1", a=5, b=2),
                AIMessage("I can only add, multiply and divide."),
            ]
        )
    )
    result = graph.invoke({"messages": [HumanMessage("5 - 2?")]}, {"recursion_limit": 10})
    tool_msg = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert tool_msg.status == "error"
    assert tool_msg.content.startswith("Error: subtract is not a valid tool")
    assert result["messages"][-1].content == "I can only add, multiply and divide."


def endless() -> Iterator[AIMessage]:
    """Yield a fresh tool call forever: a model that never stops asking."""
    for i in itertools.count(1):
        yield tool_call("add", f"call_{i}", a=i, b=1)


def test_endless_loop_hits_recursion_limit() -> None:
    """recursion_limit is the guard against a model that never stops calling tools."""
    with pytest.raises(GraphRecursionError):
        build_graph(make_model(endless())).invoke(
            {"messages": [HumanMessage("Keep adding.")]}, {"recursion_limit": 6}
        )

    nodes: list[str] = []
    with pytest.raises(GraphRecursionError):
        for update in build_graph(make_model(endless())).stream(
            {"messages": [HumanMessage("Keep adding.")]},
            {"recursion_limit": 6},
            stream_mode="updates",
        ):
            nodes.extend(update)
    assert nodes == ["call_model", "tools"] * 3

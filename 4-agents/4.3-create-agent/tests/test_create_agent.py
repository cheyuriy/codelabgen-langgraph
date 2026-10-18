"""Offline tests for the calculator agent built with create_agent."""

from collections.abc import Sequence
from typing import Any

import pytest
from l4_3_create_agent.agent import build_agent, edges
from l4_3_create_agent.chatbot import (
    SYSTEM_PROMPT,
    ToolCallingFakeModel,
    build_graph,
    make_model,
    tool_call,
    unanswered_tool_calls,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatResult
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

QUESTION = "What is (3 + 4) * 2 / 7?"


def script() -> list[AIMessage]:
    """Section (a)'s script, built fresh each time (the fake mutates the messages)."""
    return [
        tool_call("add", "call_1", a=3, b=4),
        tool_call("multiply", "call_2", a=7, b=2),
        tool_call("divide", "call_3", a=14, b=7),
        AIMessage("(3 + 4) * 2 / 7 is 2.0."),
    ]


def parallel_script() -> list[AIMessage]:
    """Section (c)'s script: one reply with two tool calls, then the answer."""
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


def ask(question: str = QUESTION) -> dict:
    """Return the graph input for one question."""
    return {"messages": [HumanMessage(question)]}


def stream_nodes(graph: CompiledStateGraph, question: str, limit: int) -> list[str]:
    """Stream a run with stream_mode='updates' and return the node names in order."""
    nodes: list[str] = []
    for update in graph.stream(ask(question), {"recursion_limit": limit}, stream_mode="updates"):
        nodes.extend(update)
    return nodes


def test_same_result_as_hand_built_graph() -> None:
    """The agent and build_graph produce the same messages for the same script."""
    agent_msgs = build_agent(make_model(script())).invoke(ask(), {"recursion_limit": 10})[
        "messages"
    ]
    hand_msgs = build_graph(make_model(script())).invoke(ask(), {"recursion_limit": 10})["messages"]
    expected_types = ["human", "ai", "tool", "ai", "tool", "ai", "tool", "ai"]
    assert [m.type for m in agent_msgs] == expected_types
    assert [m.type for m in hand_msgs] == expected_types
    assert [m.content for m in agent_msgs] == [m.content for m in hand_msgs]

    tool_msgs = [m for m in agent_msgs if isinstance(m, ToolMessage)]
    assert [m.content for m in tool_msgs] == ["7", "14", "2.0"]
    assert [m.tool_call_id for m in tool_msgs] == ["call_1", "call_2", "call_3"]
    assert agent_msgs[-1].content == "(3 + 4) * 2 / 7 is 2.0."
    assert not agent_msgs[-1].tool_calls


def test_loop_shape_and_recursion_limit() -> None:
    """Seven super-steps: limit 7 fails, 8 works; the default limit is 9999."""
    nodes = stream_nodes(build_agent(make_model(script())), QUESTION, 10)
    assert nodes == ["model", "tools", "model", "tools", "model", "tools", "model"]

    with pytest.raises(GraphRecursionError):
        build_agent(make_model(script())).invoke(ask(), {"recursion_limit": 7})
    result = build_agent(make_model(script())).invoke(ask(), {"recursion_limit": 8})
    assert result["messages"][-1].content == "(3 + 4) * 2 / 7 is 2.0."

    assert build_agent(make_model([])).config["recursion_limit"] == 9999


# Filled by RecordingModel. Module-level because the model is a pydantic
# object, which does not accept new attributes.
BIND_CALLS: list[tuple[list[str], dict[str, Any]]] = []
MODEL_INPUTS: list[list[BaseMessage]] = []


class RecordingModel(ToolCallingFakeModel):
    """The lesson's fake model, recording bind_tools calls and model inputs."""

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "RecordingModel":
        """Record the tool names and keyword arguments, then return self."""
        BIND_CALLS.append(([t.name for t in tools], kwargs))
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the messages the model receives, then answer from the script."""
        MODEL_INPUTS.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def test_what_the_model_receives() -> None:
    """bind_tools runs on every model call; each call starts with the system prompt."""
    BIND_CALLS.clear()
    MODEL_INPUTS.clear()
    model = RecordingModel(messages=iter(script()))
    result = build_agent(model).invoke(ask(), {"recursion_limit": 10})

    assert len(BIND_CALLS) == 4
    for names, kwargs in BIND_CALLS:
        assert names == ["add", "multiply", "divide"]
        assert kwargs == {"tool_choice": None}

    assert len(MODEL_INPUTS) == 4
    for messages in MODEL_INPUTS:
        assert isinstance(messages[0], SystemMessage)
        assert messages[0].content == SYSTEM_PROMPT
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])


def test_it_is_a_compiled_graph() -> None:
    """create_agent returns a CompiledStateGraph with model/tools nodes."""
    agent = build_agent(make_model([]))
    assert isinstance(agent, CompiledStateGraph)
    assert edges(agent) == [
        "__start__ --> model",
        "model -.-> __end__",
        "model -.-> tools",
        "tools -.-> model",
    ]
    assert edges(build_graph(make_model([]))) == [
        "__start__ --> call_model",
        "call_model -.-> __end__",
        "call_model -.-> tools",
        "tools --> call_model",
    ]
    assert list(agent.get_output_jsonschema()["properties"]) == ["messages", "structured_response"]


def test_two_tool_calls_in_one_reply() -> None:
    """Both calls run in one super-step; the state keeps call order."""
    question = "What are 3 + 4 and 5 * 6?"
    result = build_agent(make_model(parallel_script())).invoke(
        ask(question), {"recursion_limit": 10}
    )
    messages = result["messages"]
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tool_msgs] == ["call_a", "call_b"]
    assert [m.content for m in tool_msgs] == ["7", "30"]
    assert unanswered_tool_calls(messages) == []

    # The order of the two "tools" updates in a stream varies: compare sorted.
    nodes = stream_nodes(build_agent(make_model(parallel_script())), question, 10)
    assert sorted(nodes) == ["model", "model", "tools", "tools"]

    with pytest.raises(GraphRecursionError):
        build_agent(make_model(parallel_script())).invoke(ask(question), {"recursion_limit": 3})
    result = build_agent(make_model(parallel_script())).invoke(
        ask(question), {"recursion_limit": 4}
    )
    assert result["messages"][-1].content == "3 + 4 is 7 and 5 * 6 is 30."


def test_tool_errors_behave_as_in_4_2() -> None:
    """A failing tool raises; an unknown tool becomes an error ToolMessage."""
    agent = build_agent(make_model([tool_call("divide", "call_1", a=1, b=0)]))
    with pytest.raises(ZeroDivisionError):
        agent.invoke(ask("What is 1 / 0?"), {"recursion_limit": 10})

    reply = "I can only add, multiply and divide."
    agent = build_agent(make_model([tool_call("subtract", "call_1", a=5, b=3), AIMessage(reply)]))
    messages = agent.invoke(ask("What is 5 - 3?"), {"recursion_limit": 10})["messages"]
    tool_msg = next(m for m in messages if isinstance(m, ToolMessage))
    assert tool_msg.status == "error"
    assert tool_msg.content.startswith("Error: subtract is not a valid tool")
    assert messages[-1].content == reply

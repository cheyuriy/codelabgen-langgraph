"""Offline tests for lesson 8.4: specialist agents as tools of a supervisor."""

from typing import Any

import pytest
from l8_4_supervisor_agents.fake_model import ToolCallingFakeModel, make_model, tool_call
from l8_4_supervisor_agents.scripts import (
    SHIPPING_QUESTION,
    TWO_PART_QUESTION,
    billing_script,
    shipping_script,
    supervisor_one_script,
    supervisor_two_script,
)
from l8_4_supervisor_agents.show import node_path
from l8_4_supervisor_agents.specialists import build_billing_agent, build_shipping_agent
from l8_4_supervisor_agents.supervisor import as_tool, build_supervisor
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

BILLING_ANSWER = "INV-2077 was charged twice; the extra 49.00 was refunded on 2026-10-15."
SHIPPING_ANSWER = "ORD-1042 shipped on 2026-10-14 and arrives on 2026-10-18."

RECORDED: list[list[tuple[str, Any]]] = []


class RecordingModel(ToolCallingFakeModel):
    """A fake model that records what each call receives."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
        """Record (type, content) of every input message, then reply as scripted."""
        RECORDED.append([(m.type, m.content) for m in messages])
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def two_part_supervisor(
    supervisor_replies: list[AIMessage] | None = None, billing_model: Any = None
) -> CompiledStateGraph:
    """The section 2 supervisor with fresh scripts."""
    return build_supervisor(
        make_model(supervisor_replies or supervisor_two_script()),
        build_billing_agent(billing_model or make_model(billing_script())),
        build_shipping_agent(make_model(shipping_script())),
    )


def two_part_input() -> dict[str, list[BaseMessage]]:
    """The customer's two-part question as graph input."""
    return {"messages": [HumanMessage(TWO_PART_QUESTION)]}


def split_script() -> list[AIMessage]:
    """The two specialist calls in two separate supervisor replies."""
    return [
        tool_call("ask_billing", "call_1", request="Why was INV-2077 charged twice?"),
        tool_call("ask_shipping", "call_2", request="Where is order ORD-1042?"),
        AIMessage("Both answered."),
    ]


def test_agent_becomes_a_tool() -> None:
    """A compiled agent wrapped by as_tool takes one request and returns the final answer."""
    ask = as_tool(build_billing_agent(make_model(billing_script())), "ask_billing", "d")
    assert isinstance(ask, BaseTool)
    assert ask.name == "ask_billing"
    assert list(ask.args.keys()) == ["request"]
    answer = ask.invoke({"request": "Why was INV-2077 charged twice?"})
    assert answer == BILLING_ANSWER
    assert isinstance(answer, str)


def test_two_part_question_keeps_only_answers() -> None:
    """The supervisor's history holds the two answers, none of the specialists' inner calls."""
    result = two_part_supervisor().invoke(two_part_input(), {"recursion_limit": 10})
    messages = result["messages"]
    assert [m.type for m in messages] == ["human", "ai", "tool", "tool", "ai"]
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tool_messages] == ["call_1", "call_2"]
    assert [m.name for m in tool_messages] == ["ask_billing", "ask_shipping"]
    assert [m.content for m in tool_messages] == [BILLING_ANSWER, SHIPPING_ANSWER]
    inner = {"lookup_invoice", "track_order"}
    for m in messages:
        if isinstance(m, ToolMessage):
            assert m.name not in inner
        if isinstance(m, AIMessage):
            assert not any(c["name"] in inner for c in m.tool_calls)
    finals = [m for m in messages if isinstance(m, AIMessage) and not m.tool_calls]
    assert [m.name for m in finals] == ["supervisor"]


def test_specialist_sees_only_the_request() -> None:
    """Context isolation: the billing model never sees the customer's text."""
    RECORDED.clear()
    billing_model = RecordingModel(messages=iter(billing_script()))
    two_part_supervisor(billing_model=billing_model).invoke(
        two_part_input(), {"recursion_limit": 10}
    )
    assert len(RECORDED) == 2
    assert RECORDED[0] == [
        ("system", "You are the billing specialist."),
        ("human", "Why was INV-2077 charged twice?"),
    ]
    for call in RECORDED:
        for _, content in call:
            assert "ORD-1042" not in str(content)
            assert TWO_PART_QUESTION not in str(content)


def test_nested_trace() -> None:
    """stream(subgraphs=True) shows the specialist run under the supervisor's tools node."""
    supervisor = build_supervisor(
        make_model(supervisor_one_script()),
        build_billing_agent(make_model([])),
        build_shipping_agent(make_model(shipping_script())),
    )
    pairs = []
    for ns, update in supervisor.stream(
        {"messages": [HumanMessage(SHIPPING_QUESTION)]},
        {"recursion_limit": 10},
        stream_mode="updates",
        subgraphs=True,
    ):
        if ns != ():
            assert len(ns) == 1
            assert ns[0].startswith("tools:")
        for node, node_update in update.items():
            pairs.append((node_path(ns), node))
            if ns != ():
                for m in node_update["messages"]:
                    if isinstance(m, AIMessage):
                        assert m.name == "shipping"
    assert pairs == [
        ("(root)", "model"),
        ("tools", "model"),
        ("tools", "tools"),
        ("tools", "model"),
        ("(root)", "tools"),
        ("(root)", "model"),
    ]


def test_parallel_specialists_share_a_step() -> None:
    """Both calls in one reply need 3 super-steps; split into two replies they need 5."""
    with pytest.raises(GraphRecursionError):
        two_part_supervisor().invoke(two_part_input(), {"recursion_limit": 3})
    steps = []
    for ns, update in two_part_supervisor().stream(
        two_part_input(), {"recursion_limit": 4}, stream_mode="updates", subgraphs=True
    ):
        if ns == ():
            steps.extend(update.keys())
    assert steps == ["model", "tools", "tools", "model"]

    with pytest.raises(GraphRecursionError):
        two_part_supervisor(split_script()).invoke(two_part_input(), {"recursion_limit": 5})
    result = two_part_supervisor(split_script()).invoke(two_part_input(), {"recursion_limit": 6})
    assert result["messages"][-1].content == "Both answered."


def test_unknown_specialist_gives_error_message() -> None:
    """A call to a tool that does not exist comes back to the supervisor as an error ToolMessage."""
    script = [
        tool_call("ask_returns", "call_1", request="Can I return ORD-1042?"),
        AIMessage("Sorry, I cannot help with returns."),
    ]
    supervisor = build_supervisor(
        make_model(script),
        build_billing_agent(make_model([])),
        build_shipping_agent(make_model([])),
    )
    result = supervisor.invoke(
        {"messages": [HumanMessage("Can I return ORD-1042?")]}, {"recursion_limit": 10}
    )
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].status == "error"
    assert tool_messages[0].content.startswith("Error: ask_returns is not a valid tool")
    last = result["messages"][-1]
    assert last.content == "Sorry, I cannot help with returns."
    assert last.name == "supervisor"

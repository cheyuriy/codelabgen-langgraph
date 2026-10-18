"""Offline tests for lesson 5.3: trimming, summarizing and deleting messages."""

from typing import Any

import pytest
from l5_3_message_history.chatbot import (
    SUMMARY_PREFIX,
    ToolCallingFakeModel,
    build_graph,
    model_input,
    recent_messages,
    tool_call,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import add_messages
from pydantic import Field

FIRST_SUMMARY = "The user asked for 3 + 4 (7)."
SECOND_SUMMARY = "The user asked for 3 + 4 (7), multiplied it by 2 (14) and asked for a recap."
QUESTIONS = [
    "What is 3 + 4?",
    "Now multiply that by 2.",
    "What have we computed so far?",
    "Divide that by 7.",
]


class RecordingModel(ToolCallingFakeModel):
    """A scripted fake that records every input it receives."""

    calls: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the input, then return the next scripted reply."""
        self.calls.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def make_history() -> list[BaseMessage]:
    """Build the 7-message history of turn 1 plus turn 2 in the middle of its tool call."""
    # add_messages assigns ids, as it does in a real graph run.
    return add_messages(
        [],
        [
            HumanMessage("What is 3 + 4?"),
            tool_call("add", "call_1", a=3, b=4),
            ToolMessage("7", tool_call_id="call_1", name="add"),
            AIMessage("3 + 4 is 7."),
            HumanMessage("Now multiply that by 2."),
            tool_call("multiply", "call_2", a=7, b=2),
            ToolMessage("14", tool_call_id="call_2", name="multiply"),
        ],
    )


def run_four_turns() -> tuple[list[dict], RecordingModel, RecordingModel, Any, RunnableConfig]:
    """Run the four turns of __main__ on InMemorySaver with fresh scripts."""
    script = [
        tool_call("add", "call_1", a=3, b=4),
        AIMessage("3 + 4 is 7."),
        tool_call("multiply", "call_2", a=7, b=2),
        AIMessage("7 * 2 is 14."),
        AIMessage("So far: 3 + 4 = 7, then 7 * 2 = 14."),
        tool_call("divide", "call_3", a=14, b=7),
        AIMessage("14 / 7 is 2.0."),
    ]
    summaries = [AIMessage(FIRST_SUMMARY), AIMessage(SECOND_SUMMARY)]
    model = RecordingModel(messages=iter(script))
    summarizer = RecordingModel(messages=iter(summaries))
    graph = build_graph(model, InMemorySaver(), summarizer)
    config: RunnableConfig = {"configurable": {"thread_id": "t1"}}
    results = [graph.invoke({"messages": [HumanMessage(q)]}, config) for q in QUESTIONS]
    return results, model, summarizer, graph, config


def test_trimming_does_not_touch_state() -> None:
    """model_input trims the request; the history itself keeps every message."""
    history = make_history()
    request = model_input({"messages": history})
    assert [m.type for m in request] == ["system", "human", "ai", "tool"]
    humans = [m for m in request if isinstance(m, HumanMessage)]
    assert [m.content for m in humans] == ["Now multiply that by 2."]
    assert len(history) == 7
    assert SUMMARY_PREFIX not in request[0].content

    with_summary = model_input({"messages": history, "summary": FIRST_SUMMARY})
    assert isinstance(with_summary[0], SystemMessage)
    assert SUMMARY_PREFIX in with_summary[0].content
    assert FIRST_SUMMARY in with_summary[0].content


def test_tool_pairs_stay_together() -> None:
    """Every window starts at a HumanMessage and keeps each ToolMessage's tool call."""
    history = make_history()
    for end in range(len(history) + 1):
        prefix = history[:end]
        for n in range(1, 9):
            window = recent_messages(prefix, n)
            if not window:
                continue
            assert isinstance(window[0], HumanMessage)
            seen_call_ids: set[str] = set()
            for m in window:
                if isinstance(m, AIMessage):
                    seen_call_ids.update(c["id"] for c in m.tool_calls)
                if isinstance(m, ToolMessage):
                    assert m.tool_call_id in seen_call_ids

    # Without start_on, a window of 5 begins with an orphan ToolMessage.
    unsafe = trim_messages(history, strategy="last", token_counter=len, max_tokens=5)
    assert isinstance(unsafe[0], ToolMessage)


def test_summary_only_past_threshold_and_old_messages_deleted() -> None:
    """Turns 2 and 4 summarize and delete old turns; turns 1 and 3 do not."""
    results, _, _, graph, config = run_four_turns()
    turn1, turn2, turn3, turn4 = results

    assert len(turn1["messages"]) == 4
    assert "summary" not in turn1

    assert len(turn2["messages"]) == 4
    assert turn2["messages"][0].content == "Now multiply that by 2."
    assert turn2["summary"] == FIRST_SUMMARY

    assert len(turn3["messages"]) == 6
    assert turn3["summary"] == FIRST_SUMMARY

    assert len(turn4["messages"]) == 4
    assert turn4["messages"][0].content == "Divide that by 7."
    assert turn4["summary"] == SECOND_SUMMARY

    saved = graph.get_state(config).values
    assert len(saved["messages"]) == 4
    assert saved["summary"] == SECOND_SUMMARY


def test_what_the_models_received() -> None:
    """The model gets trimmed inputs; the summarizer gets only the old messages."""
    _, model, summarizer, _, _ = run_four_turns()

    assert [len(c) for c in model.calls] == [2, 4, 6, 4, 6, 4, 6]
    for call in model.calls:
        assert isinstance(call[0], SystemMessage)
        assert isinstance(call[1], HumanMessage)

    assert [len(c) for c in summarizer.calls] == [5, 7]
    first, second = summarizer.calls
    assert first[-1].content == "Summarize the conversation above."
    assert f"This is the summary so far: {FIRST_SUMMARY}" in second[-1].content
    assert second[0].content == "Now multiply that by 2."
    assert [m.type for m in second[:-1]] == ["human", "ai", "tool", "ai", "human", "ai"]


def test_remove_message_needs_a_real_id() -> None:
    """RemoveMessage deletes by an existing id and rejects unknown ids."""
    history = make_history()
    remaining = add_messages(history, [RemoveMessage(id=history[0].id)])
    assert len(remaining) == 6
    assert history[0].id not in {m.id for m in remaining}

    with pytest.raises(ValueError, match="doesn't exist"):
        add_messages(history, [RemoveMessage(id="nope")])


def test_long_turn_skips_the_summary() -> None:
    """A turn with two tool calls past the threshold leaves the history intact."""
    script = [
        tool_call("add", "call_1", a=3, b=4),
        AIMessage("3 + 4 is 7."),
        # One reply with two parallel tool calls: turn 2 is human ai tool tool ai.
        AIMessage(
            content="",
            tool_calls=[
                {"name": "multiply", "args": {"a": 7, "b": 2}, "id": "call_2"},
                {"name": "add", "args": {"a": 7, "b": 2}, "id": "call_3"},
            ],
        ),
        AIMessage("7 * 2 is 14 and 7 + 2 is 9."),
    ]
    model = RecordingModel(messages=iter(script))
    summarizer = RecordingModel(messages=iter([AIMessage(FIRST_SUMMARY)]))
    graph = build_graph(model, InMemorySaver(), summarizer)
    config: RunnableConfig = {"configurable": {"thread_id": "t1"}}
    graph.invoke({"messages": [HumanMessage(QUESTIONS[0])]}, config)
    turn2 = graph.invoke({"messages": [HumanMessage("Multiply it by 2 and add 2.")]}, config)

    # 9 messages is past SUMMARIZE_AFTER, but the newest 4 (ai tool tool ai)
    # hold no HumanMessage, so summarize skips instead of deleting everything.
    types = [m.type for m in turn2["messages"]]
    assert types == ["human", "ai", "tool", "ai", "human", "ai", "tool", "tool", "ai"]
    assert turn2["messages"][-1].content == "7 * 2 is 14 and 7 + 2 is 9."
    assert "summary" not in turn2
    assert summarizer.calls == []

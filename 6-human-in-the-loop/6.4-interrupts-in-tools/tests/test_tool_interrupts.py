"""Offline tests for lesson 6.4: interrupt() inside a tool of the agent loop."""

from collections.abc import Iterator
from typing import Any

import pytest
from l6_4_interrupts_in_tools import todos
from l6_4_interrupts_in_tools.agent import asks_for, build_agent, make_model
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def config(thread_id: str) -> dict[str, dict[str, str]]:
    """Return a config for the given thread."""
    return {"configurable": {"thread_id": thread_id}}


def tool_messages(messages: list[Any]) -> list[ToolMessage]:
    """Return the ToolMessages of a message list, in order."""
    return [m for m in messages if isinstance(m, ToolMessage)]


@pytest.fixture(autouse=True)
def reset_list() -> Iterator[None]:
    """Reset the module-level list, counters and id map before each test."""
    todos.reset_todo_list()
    yield


def test_add_never_pauses_and_unknown_delete_needs_no_approval() -> None:
    """add_task runs freely; delete_task of an unknown task answers without pausing."""
    graph = build_agent(
        make_model([asks_for(("add_task", "call_1", {"title": "pay rent"})), AIMessage("Added.")]),
        InMemorySaver(),
    )
    out = graph.invoke({"messages": [HumanMessage("Add pay rent")]}, config("add"), version="v2")
    assert out.interrupts == ()
    assert [m.content for m in tool_messages(out.value["messages"])] == ["Added task 3: pay rent"]
    assert todos.TODO_LIST == {1: "buy milk", 2: "call the bank", 3: "pay rent"}
    assert graph.get_state(config("add")).next == ()

    graph = build_agent(
        make_model(
            [asks_for(("delete_task", "call_9", {"task_id": 9})), AIMessage("No such task.")]
        ),
        InMemorySaver(),
    )
    out = graph.invoke({"messages": [HumanMessage("Delete 9")]}, config("unknown"), version="v2")
    assert out.interrupts == ()
    assert [m.content for m in tool_messages(out.value["messages"])] == ["There is no task 9."]


def test_delete_pauses_in_tools_node_and_resumes_with_tool_result() -> None:
    """The pause is in the "tools" task; on resume only the tools node runs again."""
    # Exactly two replies: if the model were called again on resume, the run would fail.
    graph = build_agent(
        make_model([asks_for(("delete_task", "call_2", {"task_id": 1})), AIMessage("Deleted.")]),
        InMemorySaver(),
    )
    cfg = config("approve")
    out = graph.invoke({"messages": [HumanMessage("Delete buy milk")]}, cfg, version="v2")
    assert len(out.interrupts) == 1
    assert out.interrupts[0].value == {
        "tool": "delete_task",
        "task_id": 1,
        "title": "buy milk",
        "question": "Delete task 1 'buy milk'? Answer 'yes' to confirm.",
    }
    snap = graph.get_state(cfg)
    assert snap.next == ("tools",)
    assert [t.name for t in snap.tasks] == ["tools"]
    assert [m.type for m in snap.values["messages"]] == ["human", "ai"]
    assert snap.values["messages"][-1].tool_calls[0]["id"] == "call_2"
    assert 1 in todos.TODO_LIST

    out = graph.invoke(Command(resume="yes"), cfg, version="v2")
    assert out.interrupts == ()
    messages = out.value["messages"]
    assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
    tool_message = messages[2]
    assert tool_message.content == "Deleted task 1: buy milk"
    assert tool_message.tool_call_id == "call_2"
    assert tool_message.name == "delete_task"
    assert tool_message.status == "success"
    assert 1 not in todos.TODO_LIST
    assert todos.TOOL_RUNS["delete_task"] == 2


@pytest.mark.parametrize("answer", ["no, I still need to do it", "Yes", {"approved": True}])
def test_any_answer_but_yes_is_a_rejection(answer: Any) -> None:
    """Anything but the exact "yes" comes back to the model as a normal tool result."""
    graph = build_agent(
        make_model([asks_for(("delete_task", "call_2", {"task_id": 1})), AIMessage("Kept it.")]),
        InMemorySaver(),
    )
    cfg = config("reject")
    graph.invoke({"messages": [HumanMessage("Delete buy milk")]}, cfg, version="v2")
    out = graph.invoke(Command(resume=answer), cfg, version="v2")
    assert out.interrupts == ()
    messages = out.value["messages"]
    (tool_message,) = tool_messages(messages)
    assert tool_message.status == "success"
    assert tool_message.content == f"Not deleted: the user answered {answer!r}"
    assert isinstance(messages[-1], AIMessage)
    assert messages[-1].content == "Kept it."
    assert todos.TODO_LIST == {1: "buy milk", 2: "call the bank"}


def test_sibling_tool_call_reruns_on_resume_and_stays_idempotent() -> None:
    """add_task next to delete_task runs again on resume but adds its task once."""
    graph = build_agent(
        make_model(
            [
                asks_for(
                    ("add_task", "call_4", {"title": "water the plants"}),
                    ("delete_task", "call_5", {"task_id": 1}),
                ),
                AIMessage("Done."),
            ]
        ),
        InMemorySaver(),
    )
    cfg = config("parallel")
    out = graph.invoke({"messages": [HumanMessage("Add and delete")]}, cfg, version="v2")
    assert len(out.interrupts) == 1
    assert [m.type for m in graph.get_state(cfg).values["messages"]] == ["human", "ai"]
    assert todos.TOOL_RUNS["add_task"] == 1
    assert todos.TODO_LIST[3] == "water the plants"

    out = graph.invoke(Command(resume="yes"), cfg, version="v2")
    assert todos.TOOL_RUNS["add_task"] == 2
    assert todos.TODO_LIST == {2: "call the bank", 3: "water the plants"}
    results = tool_messages(out.value["messages"])
    assert [m.tool_call_id for m in results] == ["call_4", "call_5"]
    assert [m.content for m in results] == [
        "Added task 3: water the plants",
        "Deleted task 1: buy milk",
    ]


def test_main_output(capsys: pytest.CaptureFixture[str]) -> None:
    """The live run shows the pause, the rejection and the idempotent re-run."""
    from l6_4_interrupts_in_tools.__main__ import main

    main()
    printed = capsys.readouterr().out
    assert "saved: next=('tools',) tasks=['tools']" in printed
    assert "delete_task runs: 2" in printed
    assert (
        "tool [call_3] delete_task: Not deleted: the user answered 'no, I still need to do it'"
        in printed
    )
    assert printed.rstrip().endswith(
        "add_task ran 2x, to-do list: {2: 'call the bank', 4: 'water the plants'}"
    )

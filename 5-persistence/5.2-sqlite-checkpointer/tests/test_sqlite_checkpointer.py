"""Offline tests for lesson 5.2: the calculator agent with a SQLite checkpointer."""

import subprocess
import sys
from pathlib import Path

import pytest
from l5_2_sqlite_checkpointer.__main__ import CalculatorClient
from l5_2_sqlite_checkpointer.chatbot import build_graph, make_model, tool_call
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

PACKAGE = "l5_2_sqlite_checkpointer"


def turn1_script() -> list[AIMessage]:
    """Return a fresh script for turn 1 (the fake mutates the messages)."""
    return [tool_call("add", "call_1", a=3, b=4), AIMessage("3 + 4 is 7.")]


def run_child(step: str, db: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run one step of the lesson in a new Python process."""
    return subprocess.run(
        [sys.executable, "-m", PACKAGE, step, db], capture_output=True, text=True, check=check
    )


def test_resume_from_file_with_new_saver(tmp_path: Path) -> None:
    """A new saver on the same file continues the thread saved by an earlier one."""
    db = str(tmp_path / "checkpoints.sqlite")
    config: RunnableConfig = {"configurable": {"thread_id": "chat-1"}}

    with SqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(make_model(turn1_script()), saver)
        graph.invoke({"messages": [HumanMessage("What is 3 + 4?")]}, config)

    with SqliteSaver.from_conn_string(db) as saver:
        script = [tool_call("multiply", "call_2", a=7, b=2), AIMessage("7 * 2 is 14.")]
        graph = build_graph(make_model(script), saver)
        assert len(graph.get_state(config).values["messages"]) == 4
        result = graph.invoke({"messages": [HumanMessage("Now multiply that by 2.")]}, config)
        types = [m.type for m in result["messages"]]
        assert types == ["human", "ai", "tool", "ai", "human", "ai", "tool", "ai"]
        assert result["messages"][-1].content == "7 * 2 is 14."
        assert len(list(saver.list(config))) == 10


def test_two_real_processes(tmp_path: Path) -> None:
    """Turn 2 in a second process loads turn 1 from the file."""
    db = str(tmp_path / "checkpoints.sqlite")
    out1 = run_child("turn1", db).stdout
    out2 = run_child("turn2", db).stdout
    assert "loaded from the file: 0 messages" in out1
    assert "loaded from the file: 4 messages" in out2
    assert "the thread now holds 8 messages in 10 checkpoints" in out2

    with SqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(make_model([]), saver)
        snap = graph.get_state({"configurable": {"thread_id": "chat-1"}})
        assert len(snap.values["messages"]) == 8
        assert snap.next == ()


def test_durability_modes() -> None:
    """All modes give the same result; exit saves one checkpoint instead of five."""
    with SqliteSaver.from_conn_string(":memory:") as saver:
        for mode in ("sync", "async", "exit"):
            config: RunnableConfig = {"configurable": {"thread_id": f"d-{mode}"}}
            graph = build_graph(make_model(turn1_script()), saver)
            result = graph.invoke(
                {"messages": [HumanMessage("What is 3 + 4?")]}, config, durability=mode
            )
            assert len(result["messages"]) == 4
            assert len(graph.get_state(config).values["messages"]) == 4

            saved = list(saver.list(config))
            if mode == "exit":
                assert len(saved) == 1
                assert saved[0].metadata["step"] == 3
                assert saved[0].metadata["source"] == "loop"
            else:
                assert [c.metadata["step"] for c in saved] == [3, 2, 1, 0, -1]


def test_hard_crash_per_mode(tmp_path: Path) -> None:
    """A killed process keeps its finished steps with sync and nothing with exit."""
    db = str(tmp_path / "checkpoints.sqlite")
    assert run_child("crash-sync", db, check=False).returncode == 1
    assert run_child("crash-exit", db, check=False).returncode == 1

    with SqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(make_model([]), saver)

        sync_config: RunnableConfig = {"configurable": {"thread_id": "crash-sync"}}
        snap = graph.get_state(sync_config)
        assert len(snap.values["messages"]) == 3
        assert snap.next == ("call_model",)
        assert snap.metadata is not None
        assert snap.metadata["step"] == 2
        assert len(list(saver.list(sync_config))) == 4

        exit_config: RunnableConfig = {"configurable": {"thread_id": "crash-exit"}}
        snap = graph.get_state(exit_config)
        assert snap.values == {}
        assert snap.next == ()
        assert list(saver.list(exit_config)) == []


def test_thread_rules(tmp_path: Path) -> None:
    """A thread_id is required, and SqliteSaver stores it as text."""
    db = str(tmp_path / "checkpoints.sqlite")
    with SqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(make_model(turn1_script()), saver)
        with pytest.raises(ValueError, match="thread_id"):
            graph.invoke({"messages": [HumanMessage("What is 3 + 4?")]})

        graph = build_graph(make_model(turn1_script()), saver)
        graph.invoke(
            {"messages": [HumanMessage("What is 3 + 4?")]}, {"configurable": {"thread_id": 1}}
        )
        snap = graph.get_state({"configurable": {"thread_id": "1"}})
        assert len(snap.values["messages"]) == 4


def test_serialization(tmp_path: Path) -> None:
    """The checkpoint serializer saves messages and rejects live objects."""
    db = str(tmp_path / "checkpoints.sqlite")
    with SqliteSaver.from_conn_string(db) as saver:
        kind, data = saver.serde.dumps_typed(HumanMessage("hi"))
        assert kind == "msgpack"
        restored = saver.serde.loads_typed((kind, data))
        assert isinstance(restored, HumanMessage)
        assert restored.content == "hi"

        with pytest.raises(TypeError, match="not msgpack serializable"):
            saver.serde.dumps_typed(CalculatorClient())

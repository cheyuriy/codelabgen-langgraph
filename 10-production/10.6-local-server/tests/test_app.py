"""Offline tests for lesson 10.6: the factory, langgraph.json and the launcher, without a server."""

import socket
from pathlib import Path

import l10_6_local_server.graph as graph_module
import pytest
from l10_6_local_server import server
from l10_6_local_server.client import ASSISTANT, ticket
from l10_6_local_server.graph import make_graph
from l10_6_local_server.server import running_server
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph_cli.config import validate_config_file

LESSON_DIR = Path(__file__).resolve().parents[1]


def test_factory_builds_graph_without_checkpointer() -> None:
    """make_graph returns a fresh compiled graph with no checkpointer of its own."""
    g = make_graph()
    assert isinstance(g, CompiledStateGraph)
    assert g.checkpointer is None
    # The server calls the factory per run, so each call builds a new graph.
    assert make_graph() is not make_graph()


def test_langgraph_json_is_valid() -> None:
    """langgraph.json passes the CLI's own validation and points at make_graph."""
    cfg = validate_config_file(LESSON_DIR / "langgraph.json")
    assert cfg["graphs"] == {ASSISTANT: "./src/l10_6_local_server/graph.py:make_graph"}
    assert cfg["dependencies"] == ["."]
    assert cfg["python_version"] == "3.12"
    file_part, name = cfg["graphs"][ASSISTANT].split(":")
    assert (LESSON_DIR / file_part).is_file()
    assert callable(getattr(graph_module, name))


@pytest.mark.parametrize(
    ("text", "category", "name", "content"),
    [
        (
            "Please refund invoice INV-1042",
            "billing",
            "billing",
            "Billing team: the refund for INV-1042 is on its way.",
        ),
        (
            "Where is my parcel?",
            "general",
            "general",
            "Support team: thanks, we will get back to you.",
        ),
    ],
    ids=["billing", "general"],
)
def test_json_ticket_runs_in_process(text: str, category: str, name: str, content: str) -> None:
    """The JSON-style input the client sends also works without a server."""
    result = make_graph().invoke(ticket(text))
    assert result["category"] == category
    # add_messages turned the JSON dict into a HumanMessage.
    assert isinstance(result["messages"][0], HumanMessage)
    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    assert last.name == name
    assert last.content == content


def test_running_server_refuses_busy_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """A busy port is refused before any `langgraph dev` process is started."""

    def no_popen(*args: object, **kwargs: object) -> None:
        pytest.fail("running_server started a process on a busy port")

    monkeypatch.setattr(server.subprocess, "Popen", no_popen)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(RuntimeError, match="already in use"):
            with running_server(port):
                pass

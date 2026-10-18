"""Level 2: run the whole graph, with a fresh checkpointer and fake model per test."""

import pytest
from l10_5_testing_graphs.graph import build_graph
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver


# region test_full_run
@pytest.mark.parametrize(
    ("text", "category", "team", "reply"),
    [
        pytest.param(
            "Please refund my order",
            "billing",
            "Billing team",
            "We will check your refund today.",
            id="billing",
        ),
        pytest.param(
            "The app crashes on login",
            "tech",
            "Tech team",
            "Sorry about the crash, we are on it.",
            id="tech",
        ),
        pytest.param(
            "Do you ship to Canada?",
            "general",
            "Support team",
            "Thanks for asking, we will get back to you.",
            id="general",
        ),
    ],
)
def test_full_run(
    make_model,
    checkpointer: InMemorySaver,
    config: RunnableConfig,
    text: str,
    category: str,
    team: str,
    reply: str,
) -> None:
    """A ticket goes from START to END and every node leaves its key."""
    # One scripted reply, because the run makes exactly one model call.
    model = make_model(reply)
    graph = build_graph(model, checkpointer)

    result = graph.invoke({"text": text}, config)

    assert result == {
        "text": text,
        "category": category,
        "team": team,
        "reply": reply,
        "status": "sent",
    }
    assert len(model.prompts) == 1
    # Nothing is left to run on this thread: the graph reached END.
    assert graph.get_state(config).next == ()


# endregion


# region test_route_order
def test_route_order(make_model, checkpointer: InMemorySaver, config: RunnableConfig) -> None:
    """Only one queue node runs, and the nodes run in wiring order."""
    graph = build_graph(make_model("Thanks for asking."), checkpointer)

    # stream_mode="updates" yields one {node_name: update} dict per step.
    chunks = graph.stream({"text": "Do you ship to Canada?"}, config, stream_mode="updates")
    order = [name for chunk in chunks for name in chunk]

    assert order == ["classify", "general_queue", "draft_reply", "send_reply"]


# endregion

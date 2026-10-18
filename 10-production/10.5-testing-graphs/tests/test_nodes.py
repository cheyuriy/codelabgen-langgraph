"""Level 1: test one node at a time through the compiled graph.

compiled_graph.nodes maps node names (plus "__start__") to PregelNode
objects. node.invoke(state) runs only that node and returns its update.
"""

import pytest
from l10_5_testing_graphs.graph import build_graph
from langgraph.checkpoint.memory import InMemorySaver


# region test_classify_node
@pytest.mark.parametrize(
    ("text", "category"),
    [
        pytest.param("Please refund my order", "billing", id="refund-billing"),
        pytest.param("The app crashes on login", "tech", id="crash-tech"),
        pytest.param("Do you ship to Canada?", "general", id="question-general"),
        pytest.param("Payment page shows an error", "billing", id="billing-before-tech"),
    ],
)
def test_classify_node(make_model, text: str, category: str) -> None:
    """classify sorts tickets by keywords and never calls the model."""
    # An empty script: any model call would fail, so a green test proves that
    # classify does not touch the model.
    graph = build_graph(make_model())

    update = graph.nodes["classify"].invoke({"text": text})

    # The node returns only its own key, not the whole state.
    assert update == {"category": category}


# endregion


# region test_draft_reply_node
def test_draft_reply_node(make_model, checkpointer: InMemorySaver) -> None:
    """draft_reply sends the team prompt and the ticket to the model."""
    model = make_model("Sorry about the crash, we are on it.")
    graph = build_graph(model, checkpointer)

    # The node gets exactly the state it reads; no other node runs.
    update = graph.nodes["draft_reply"].invoke(
        {"text": "The app crashes on login", "team": "Tech team"}
    )

    assert update == {"reply": "Sorry about the crash, we are on it."}
    assert [m.content for m in model.prompts[0]] == [
        "You write short, friendly replies for the Tech team.",
        "The app crashes on login",
    ]
    # A direct node call bypasses the graph's checkpointer: nothing was saved.
    assert list(checkpointer.list(None)) == []


# endregion

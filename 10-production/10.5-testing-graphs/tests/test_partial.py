"""Level 3: run only a slice of the graph.

update_state(config, values, as_node="classify") saves the values as if
classify had just finished, so the run continues at the queue node that
route_ticket picks. interrupt_after stops the run before send_reply.
"""

from l10_5_testing_graphs.graph import build_graph
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

FAKE_REPLY = "Sorry about the crash, we are on it."


# region test_partial_run
def test_partial_run(make_model, checkpointer: InMemorySaver, config: RunnableConfig) -> None:
    """Start after classify, stop after draft_reply: send_reply never runs."""
    model = make_model(FAKE_REPLY)
    graph = build_graph(model, checkpointer)

    # The seeded category contradicts the text on purpose: the text says
    # "refund", but the tech route proves classify did not run and the seeded
    # state decided the route.
    graph.update_state(
        config,
        {"text": "Please refund my order", "category": "tech"},
        as_node="classify",
    )

    # Pass None: new input would start a new run at START. interrupt_after
    # takes a list of node names.
    result = graph.invoke(None, config, interrupt_after=["draft_reply"])

    assert result["team"] == "Tech team"
    assert result["reply"] == FAKE_REPLY
    assert "status" not in result
    # An unknown node name in interrupt_after is silently ignored, so check
    # where the run stopped: the next node to run is send_reply.
    assert graph.get_state(config).next == ("send_reply",)
    assert model.prompts[0][0].content == ("You write short, friendly replies for the Tech team.")


# endregion


# region test_resume_after_partial
def test_resume_after_partial(
    make_model, checkpointer: InMemorySaver, config: RunnableConfig
) -> None:
    """Resuming after the stop runs only send_reply and reuses the draft."""
    model = make_model(FAKE_REPLY)
    graph = build_graph(model, checkpointer)
    graph.update_state(
        config,
        {"text": "Please refund my order", "category": "tech"},
        as_node="classify",
    )
    graph.invoke(None, config, interrupt_after=["draft_reply"])

    # None again: continue the saved thread from where it stopped.
    updates = list(graph.stream(None, config, stream_mode="updates"))

    assert updates == [{"send_reply": {"status": "sent"}}]
    # The draft is not regenerated: the model was called only once.
    assert len(model.prompts) == 1
    assert graph.get_state(config).next == ()


# endregion

"""A small ticket router, built so it is easy to test.

START -> classify -> {billing_queue | tech_queue | general_queue}
      -> draft_reply -> send_reply -> END

The only LLM step (draft_reply) gets its chat model as a parameter, and the
graph is built by a factory. Both choices exist for the tests in ``tests/``.
"""

from collections.abc import Callable
from typing import Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

# Billing is checked first: "Payment page shows an error" is a billing ticket.
BILLING_KEYWORDS = ("refund", "invoice", "charge", "payment")
TECH_KEYWORDS = ("error", "crash", "down", "bug", "login")

# The system prompt names the team, so a test can see which queue ran.
SYSTEM_PROMPT = "You write short, friendly replies for the {team}."

Category = Literal["billing", "tech", "general"]


# region state
class TicketState(TypedDict):
    """The state shared by all nodes. Each node writes only its own keys."""

    text: str  # the ticket as the customer typed it
    category: Category  # set by classify
    team: str  # set by the queue node that ran
    reply: str  # set by draft_reply
    status: str  # set by send_reply


# endregion


# region classify_node
def classify(state: TicketState) -> dict[str, str]:
    """Sort the ticket into a category by keywords. No model involved."""
    text = state["text"].lower()
    if any(word in text for word in BILLING_KEYWORDS):
        return {"category": "billing"}
    if any(word in text for word in TECH_KEYWORDS):
        return {"category": "tech"}
    return {"category": "general"}


# endregion


# region route_ticket
def route_ticket(state: TicketState) -> Category:
    """Pick the next node. LangGraph maps the returned key to a queue node."""
    return state["category"]


# endregion


# region queue_nodes
def billing_queue(state: TicketState) -> dict[str, str]:
    """Hand the ticket to the billing team."""
    return {"team": "Billing team"}


def tech_queue(state: TicketState) -> dict[str, str]:
    """Hand the ticket to the tech team."""
    return {"team": "Tech team"}


def general_queue(state: TicketState) -> dict[str, str]:
    """Hand the ticket to the general support team."""
    return {"team": "Support team"}


# endregion


# region draft_reply_node
def make_draft_reply(model: BaseChatModel) -> Callable[[TicketState], dict[str, str]]:
    """Build the draft_reply node around the given chat model.

    The model is a parameter: production passes a real chat model, tests pass
    a fake one. Nothing in the graph knows the difference.
    """

    def draft_reply(state: TicketState) -> dict[str, str]:
        """Ask the model for a reply written for the team that owns the ticket."""
        response = model.invoke(
            [
                SystemMessage(SYSTEM_PROMPT.format(team=state["team"])),
                HumanMessage(state["text"]),
            ]
        )
        return {"reply": response.content}

    return draft_reply


# endregion


# region send_reply_node
def send_reply(state: TicketState) -> dict[str, str]:
    """Mark the reply as sent.

    This stands in for the real side effect (an email or a helpdesk API call),
    the step that a test of the drafting step must not trigger.
    """
    return {"status": "sent"}


# endregion


# region build_graph
def build_graph(
    model: BaseChatModel, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    """Wire and compile the ticket router.

    A factory, not a module-level graph: every test builds its own graph with
    its own model and checkpointer, so nothing is shared between tests.
    """
    builder = StateGraph(TicketState)
    builder.add_node("classify", classify)
    builder.add_node("billing_queue", billing_queue)
    builder.add_node("tech_queue", tech_queue)
    builder.add_node("general_queue", general_queue)
    builder.add_node("draft_reply", make_draft_reply(model))
    builder.add_node("send_reply", send_reply)

    builder.add_edge(START, "classify")
    # route_ticket returns a category; the mapping turns it into a node name.
    builder.add_conditional_edges(
        "classify",
        route_ticket,
        {
            "billing": "billing_queue",
            "tech": "tech_queue",
            "general": "general_queue",
        },
    )
    # Whatever queue ran, the ticket goes on to the same drafting step.
    builder.add_edge("billing_queue", "draft_reply")
    builder.add_edge("tech_queue", "draft_reply")
    builder.add_edge("general_queue", "draft_reply")
    builder.add_edge("draft_reply", "send_reply")
    builder.add_edge("send_reply", END)
    return builder.compile(checkpointer=checkpointer)


# endregion

"""The support desk: classify a ticket, then let the billing subgraph or the general node answer."""

from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from l8_1_subgraphs_shared_state.billing import build_billing

# Words that mark a ticket as a billing question (the same list as lesson 1.2).
BILLING_KEYWORDS = ("refund", "invoice", "charge", "payment")

# The teams a ticket can go to; each value is also a key of the path map.
Category = Literal["billing", "general"]


# region desk_state
class DeskState(TypedDict):
    """State of the parent (desk) graph."""

    # Shared with the billing subgraph: same name, same reducer.
    messages: Annotated[list[AnyMessage], add_messages]
    # Exists only in the parent: the subgraph never sees it and cannot
    # overwrite it.
    category: NotRequired[Category]


# endregion


# region desk_nodes
def classify(state: DeskState) -> dict:
    """Record which team should answer the latest ticket."""
    text = state["messages"][-1].content.lower()
    is_billing = any(word in text for word in BILLING_KEYWORDS)
    return {"category": "billing" if is_billing else "general"}


def route_ticket(state: DeskState) -> Category:
    """Read the decision classify recorded, as in lesson 1.2."""
    return state["category"]


def general(state: DeskState) -> dict:
    """Answer every ticket that is not about billing."""
    reply = AIMessage("Support team: thanks, we will get back to you.", name="general")
    return {"messages": [reply]}


# endregion


# region build_desk
def build_desk(checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    """Build the desk graph with the billing subgraph as one of its nodes."""
    builder = StateGraph(DeskState)
    builder.add_node("classify", classify)
    # A compiled graph is a node like a function: no wrapper. The parent
    # passes its state in and applies what comes back. That works because the
    # two schemas share keys (messages); with no shared key the subgraph
    # would get an empty input (experiment 4). A subgraph with a different
    # schema is called inside a node function instead (lesson 8.2).
    #
    # How the result merges: when the subgraph finishes, the parent node
    # "billing" writes the subgraph's FINAL values of the shared keys as ONE
    # update, through the PARENT's reducers. Here that is the whole messages
    # list (the ticket plus the reply), not just the new reply. add_messages
    # matches messages by id, so the ticket already in the parent is
    # replaced by itself and only the reply is new; with a plain list
    # reducer such as operator.add the ticket would be appended a second
    # time (experiment 1). Keys only the subgraph has (invoice_id) are
    # dropped; keys only the parent has (category) are left alone.
    builder.add_node("billing", build_billing())
    builder.add_node("general", general)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify", route_ticket, {"billing": "billing", "general": "general"}
    )
    builder.add_edge("billing", END)
    builder.add_edge("general", END)
    # Only the parent gets the checkpointer; the parent lends it to the
    # subgraph on every run.
    return builder.compile(checkpointer=checkpointer)


# endregion

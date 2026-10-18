"""The support desk: classify a ticket, then let the billing subgraph, the tech subgraph or the
general node answer.
"""

from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from l8_2_subgraphs_own_state.billing import build_billing
from l8_2_subgraphs_own_state.tech import build_tech

# Words that mark a ticket as a billing question (the same list as lesson 1.2).
BILLING_KEYWORDS = ("refund", "invoice", "charge", "payment")
# Words that mark a ticket as a technical problem (the same list as lesson 1.2).
TECH_KEYWORDS = ("error", "crash", "down", "bug", "login")

# The teams a ticket can go to; each value is also a key of the path map.
Category = Literal["billing", "tech", "general"]


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
    if any(word in text for word in BILLING_KEYWORDS):
        return {"category": "billing"}
    if any(word in text for word in TECH_KEYWORDS):
        return {"category": "tech"}
    return {"category": "general"}


def route_ticket(state: DeskState) -> Category:
    """Read the decision classify recorded, as in lesson 1.2."""
    return state["category"]


def general(state: DeskState) -> dict:
    """Answer every ticket that is neither billing nor tech."""
    reply = AIMessage("Support team: thanks, we will get back to you.", name="general")
    return {"messages": [reply]}


# endregion


# region tech_node
# Compiled once, at import. The node function below names it, and LangGraph
# finds subgraphs inside a function node statically, by looking at the
# globals and closure variables the function uses (get_function_nonlocals in
# pregel/_utils.py). That is why get_subgraphs() lists "tech" (section 2 of
# the run) and get_state(..., subgraphs=True) can load its state (section 3).
# Build it inside the function instead and the run still works, but the desk
# can no longer see it (experiment 3).
TECH_TEAM = build_tech()


def tech(state: DeskState) -> dict:
    """Hand the ticket to the tech subgraph and turn its result into a reply."""
    # Map in: the subgraph gets only what this line builds, the ticket text
    # as problem. Passing the desk state itself would give it messages and
    # category, keys it does not have, and no problem (experiment 2).
    #
    # No config argument: LangGraph passes the running config along (the
    # thread, the lent checkpointer, the namespace "tech:<task_id>"), so the
    # inner run is saved, streamed and can pause like a subgraph added as a
    # node.
    #
    # On resume (section 4) this node runs again from its first line
    # (lessons 6.1 and 6.3), so the map-in line runs twice: keep code before
    # the invoke cheap and free of side effects. The inner invoke finds the
    # subgraph's saved checkpoint under the same namespace and continues at
    # identify_device instead of starting over.
    result = TECH_TEAM.invoke({"problem": state["messages"][-1].content})
    # Map out: invoke returns the subgraph's whole final state (problem,
    # device, fix). Only what this function returns reaches the desk, through
    # the desk's reducers: here one new message. Compare the billing node,
    # whose update is the subgraph's whole shared messages list (section 2).
    # Returning `result` as it is would be silently dropped: none of its keys
    # is a desk key (experiment 1).
    reply = f"Tech team: on your {result['device']}, {result['fix']}."
    return {"messages": [AIMessage(reply, name="tech")]}


# endregion


# region build_desk
def build_desk(checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    """Build the desk graph: billing added as a node, tech called inside a node."""
    builder = StateGraph(DeskState)
    builder.add_node("classify", classify)
    # A compiled graph is a node like a function: no wrapper. The parent
    # passes its state in and applies what comes back. That works because the
    # two schemas share keys (messages); with no shared key the subgraph
    # would get an empty input (experiment 4). A subgraph with a different
    # schema is called inside a node function instead (the tech node below).
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
    # To the desk, "tech" is an ordinary function node. When to use which:
    # add a compiled graph as a node when it shares keys with the parent
    # (billing); call it inside a node when the schemas differ or the parent
    # should see only a translated result (tech).
    builder.add_node("tech", tech)
    builder.add_node("general", general)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_ticket,
        {"billing": "billing", "tech": "tech", "general": "general"},
    )
    builder.add_edge("billing", END)
    builder.add_edge("tech", END)
    builder.add_edge("general", END)
    # Only the parent gets the checkpointer; the parent lends it to the
    # subgraph on every run.
    return builder.compile(checkpointer=checkpointer)


# endregion

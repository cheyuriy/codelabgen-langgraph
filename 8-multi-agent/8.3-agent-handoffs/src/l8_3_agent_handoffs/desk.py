"""The support desk: classify a ticket, then let the billing subgraph, the tech subgraph or the
general node answer; billing and tech can hand a ticket to each other.
"""

import operator
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from l8_3_agent_handoffs.billing import build_billing
from l8_3_agent_handoffs.handoff import ticket_text
from l8_3_agent_handoffs.tech import build_tech

# Words that mark a ticket as a billing question (the same list as lesson 1.2).
BILLING_KEYWORDS = ("refund", "invoice", "charge", "payment")
# Words that mark a ticket as a technical problem (the same list as lesson 1.2).
TECH_KEYWORDS = ("error", "crash", "down", "bug", "login")

# The teams a ticket can go to; each value is also a key of the path map.
Category = Literal["billing", "tech", "general"]


# region desk_state
class DeskState(TypedDict):
    """State of the parent (desk) graph."""

    # Shared with the billing subgraph: same name, same reducer. Handoff
    # notes from both teams are added through it too.
    messages: Annotated[list[AnyMessage], add_messages]
    # Exists only in the parent: the subgraph never sees it and cannot
    # overwrite it.
    category: NotRequired[Category]
    # A log of handoffs such as "billing -> tech", written by nodes inside
    # the subgraphs through Command.PARENT (handoff.py). A key that is
    # updated across graph levels needs a reducer in the PARENT state (the
    # docs say "must"): each update is applied through it, so operator.add
    # appends the entries of every handoff on the thread (both tickets of
    # the run, section 3). Without a reducer each handoff replaces the log:
    # no error, just a lost entry (experiment 2). It starts as [] even when
    # no ticket was handed off.
    handoffs: Annotated[list[str], operator.add]


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
# pregel/_utils.py). That is why get_subgraphs() lists "tech" and
# get_state(..., subgraphs=True) can load its state (lesson 8.2). Build it
# inside the function instead and the run still works, but the desk can no
# longer see it.
TECH_TEAM = build_tech()


def tech(state: DeskState) -> dict:
    """Hand the ticket to the tech subgraph and turn its result into a reply."""
    # Map in: the subgraph gets only what this line builds, the ticket text
    # as problem. Passing the desk state itself would give it messages and
    # category, keys it does not have, and no problem (lesson 8.2). After a
    # handoff from billing the last message is billing's note, so the ticket
    # is read with ticket_text.
    #
    # No config argument: LangGraph passes the running config along (the
    # thread, the lent checkpointer, the namespace "tech:<task_id>"), so the
    # inner run is saved, streamed and can pause like a subgraph added as a
    # node.
    #
    # On resume (lesson 8.2) this node runs again from its first line
    # (lessons 6.1 and 6.3), so the map-in line runs twice: keep code before
    # the invoke cheap and free of side effects. The inner invoke finds the
    # subgraph's saved checkpoint under the same namespace and continues at
    # identify_device instead of starting over.
    result = TECH_TEAM.invoke({"problem": ticket_text(state["messages"])})
    # Map out: invoke returns the subgraph's whole final state (problem,
    # device, fix). Only what this function returns reaches the desk, through
    # the desk's reducers: here one new message. Compare the billing node,
    # whose update is the subgraph's whole shared messages list (section 2
    # of the run). Returning `result` as it is would be silently dropped:
    # none of its keys is a desk key (lesson 8.2).
    #
    # When the tech subgraph hands off, the invoke above does not return:
    # ParentCommand unwinds through this function, so the map-out lines
    # below never run, and the desk applies the handoff's update as the
    # update of the node "tech" (section 2 shows it as the root tech line).
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
    # would get an empty input (lesson 8.1). A subgraph with a different
    # schema is called inside a node function instead (the tech node below).
    #
    # How the result merges: when the subgraph finishes, the parent node
    # "billing" writes the subgraph's FINAL values of the shared keys as ONE
    # update, through the PARENT's reducers. Here that is the whole messages
    # list (the ticket plus the reply), not just the new reply. add_messages
    # matches messages by id, so the ticket already in the parent is
    # replaced by itself and only the reply is new; with a plain list
    # reducer such as operator.add the ticket would be appended a second
    # time (lesson 8.1). Keys only the subgraph has (invoice_id) are
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
    # There is no edge billing -> tech or tech -> billing: a handoff's goto
    # adds the jump at run time. A goto does not replace static edges: the
    # edges to END stay and still fire (the docs warn about mixing both for
    # routing; here END does nothing). The desk's drawing therefore does not
    # show the handoff routes (destinations=, experiment 5).
    builder.add_edge("billing", END)
    builder.add_edge("tech", END)
    builder.add_edge("general", END)
    # Only the parent gets the checkpointer; the parent lends it to the
    # subgraph on every run.
    return builder.compile(checkpointer=checkpointer)


# endregion

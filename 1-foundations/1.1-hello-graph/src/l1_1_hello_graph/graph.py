"""A linear LangGraph pipeline that prepares a raw support ticket.

START -> clean -> tag_priority -> END

The graph shares one state dict (TicketState). Each node reads the state and
returns only the keys it owns; LangGraph merges that partial update into the
shared state before the next node runs.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

# Words that make a ticket urgent. A plain substring check is enough here.
URGENT_KEYWORDS = ("urgent", "asap", "down", "outage", "refund")


# region state
class TicketState(TypedDict):
    """The shared state every node reads from and writes to.

    Each key becomes a channel in the graph. With no reducer attached, a value
    a node returns for a key simply replaces the old value.
    """

    text: str  # the raw ticket text, as the customer typed it
    clean_text: str  # written by the clean node
    priority: str  # written by the tag_priority node: "high" or "normal"


# endregion


# region clean_node
def clean(state: TicketState) -> dict[str, str]:
    """Collapse whitespace and lowercase the raw text into clean_text."""
    # str.split() with no argument splits on any run of whitespace (spaces,
    # newlines, tabs) and drops leading/trailing whitespace.
    clean_text = " ".join(state["text"].split()).lower()
    # Return only the key this node owns: a partial update. LangGraph merges
    # it into the state, so "text" stays untouched.
    return {"clean_text": clean_text}


# endregion


# region tag_priority_node
def tag_priority(state: TicketState) -> dict[str, str]:
    """Set priority to "high" if clean_text holds an urgent keyword."""
    # clean_text is available here because the clean node ran first and its
    # update was already merged into the state.
    is_urgent = any(word in state["clean_text"] for word in URGENT_KEYWORDS)
    return {"priority": "high" if is_urgent else "normal"}


# endregion


# region build_graph
def build_graph() -> CompiledStateGraph:
    """Wire the nodes into a linear graph and compile it."""
    # The builder takes the state schema; it defines which keys exist.
    builder = StateGraph(TicketState)

    # Register each node under a string name. Order of add_node does not
    # decide what runs; only edges do.
    builder.add_node("clean", clean)
    builder.add_node("tag_priority", tag_priority)

    # START and END are the graph's virtual entry and exit points.
    builder.add_edge(START, "clean")
    builder.add_edge("clean", "tag_priority")
    builder.add_edge("tag_priority", END)

    # compile() validates the wiring (entry point, unknown node names) and
    # returns a runnable graph with invoke() and stream().
    return builder.compile()


# endregion

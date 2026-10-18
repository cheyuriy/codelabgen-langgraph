"""A LangGraph pipeline that prepares a support ticket and routes it to a queue.

START -> clean -> tag_priority -> classify -(conditional)->
    {billing_queue | tech_queue | general_queue} -> END

The graph shares one state dict (TicketState). Each node reads the state and
returns only the keys it owns; LangGraph merges that partial update into the
shared state before the next node runs. After classify, a conditional edge
picks exactly one queue node, so only one of them runs per ticket.
"""

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

# Words that make a ticket urgent. A plain substring check is enough here.
URGENT_KEYWORDS = ("urgent", "asap", "down", "outage", "refund")
# Words that send a ticket to the billing queue (checked first).
BILLING_KEYWORDS = ("refund", "invoice", "charge", "payment")
# Words that send a ticket to the tech queue (checked after billing).
TECH_KEYWORDS = ("error", "crash", "down", "bug", "login")

# The labels the routing function may return. The Literal type documents every
# possible route in one place.
Category = Literal["billing", "tech", "general"]


# region state
class TicketState(TypedDict):
    """The shared state every node reads from and writes to.

    Each key becomes a channel in the graph. With no reducer attached, a value
    a node returns for a key simply replaces the old value.
    """

    text: str  # the raw ticket text, as the customer typed it
    clean_text: str  # written by the clean node
    priority: str  # written by the tag_priority node: "high" or "normal"
    category: Category  # written by the classify node
    reply: str  # written by whichever queue node ran


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


# region classify_node
def classify(state: TicketState) -> dict[str, str]:
    """Write the ticket's category: billing, then tech, otherwise general."""
    text = state["clean_text"]
    # Order matters: a ticket that mentions both a payment and an error is
    # treated as a billing ticket because billing is checked first.
    if any(word in text for word in BILLING_KEYWORDS):
        category = "billing"
    elif any(word in text for word in TECH_KEYWORDS):
        category = "tech"
    else:
        category = "general"
    # The decision is stored in the state, so it shows up in the final result
    # and in the stream, and it can be tested on its own.
    return {"category": category}


# endregion


# region route_ticket
def route_ticket(state: TicketState) -> Category:
    """Return the route label for the conditional edge out of classify."""
    # A routing function returns a destination label, not a state update.
    # It only reads the state and never changes it; the decision itself was
    # recorded by the classify node so it is visible in the result and
    # testable.
    return state["category"]


# endregion


# region queue_nodes
def billing_queue(state: TicketState) -> dict[str, str]:
    """Answer a billing ticket with the billing team's fixed reply."""
    return {"reply": "Billing team: we will check your invoice."}


def tech_queue(state: TicketState) -> dict[str, str]:
    """Answer a tech ticket with the tech team's fixed reply."""
    return {"reply": "Tech team: we are looking into the problem."}


def general_queue(state: TicketState) -> dict[str, str]:
    """Answer any other ticket with the support team's fixed reply."""
    return {"reply": "Support team: thanks, we will get back to you."}


# endregion


# region build_graph
def build_graph() -> CompiledStateGraph:
    """Wire the nodes into a graph with one conditional edge and compile it."""
    # The builder takes the state schema; it defines which keys exist.
    builder = StateGraph(TicketState)

    # Register each node under a string name. Order of add_node does not
    # decide what runs; only edges do.
    builder.add_node("clean", clean)
    builder.add_node("tag_priority", tag_priority)
    builder.add_node("classify", classify)
    builder.add_node("billing_queue", billing_queue)
    builder.add_node("tech_queue", tech_queue)
    builder.add_node("general_queue", general_queue)

    # START and END are the graph's virtual entry and exit points.
    builder.add_edge(START, "clean")
    builder.add_edge("clean", "tag_priority")
    builder.add_edge("tag_priority", "classify")

    # After classify, LangGraph calls route_ticket and follows exactly one
    # path. The path map translates the labels route_ticket returns into node
    # names and declares every possible destination, so compile() can check
    # them and get_graph() can draw them. The Literal return type documents
    # the same labels and is what LangGraph would use as destinations if
    # there were no path map.
    builder.add_conditional_edges(
        "classify",
        route_ticket,
        {"billing": "billing_queue", "tech": "tech_queue", "general": "general_queue"},
    )

    # Whichever queue node ran, the graph ends after it.
    builder.add_edge("billing_queue", END)
    builder.add_edge("tech_queue", END)
    builder.add_edge("general_queue", END)

    # compile() validates the wiring (entry point, unknown node names) and
    # returns a runnable graph with invoke() and stream().
    return builder.compile()


# endregion

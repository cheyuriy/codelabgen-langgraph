"""The billing team as its own small graph; the desk adds it as one node."""

import re
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from l8_3_agent_handoffs.handoff import hand_off, ticket_text

# Words that tell billing a ticket is really a technical problem. The
# billing team keeps its own list: importing the desk's TECH_KEYWORDS
# would be a circular import (desk.py imports this module).
TECH_WORDS = ("error", "crash", "bug")


# region billing_state
class BillingState(TypedDict):
    """State of the billing subgraph."""

    # Same name AND same reducer as in DeskState. A key with the same name is
    # the channel parent and subgraph share: the subgraph gets the parent's
    # value as its input and hands its final value back when it finishes.
    messages: Annotated[list[AnyMessage], add_messages]
    # Private to the subgraph: the parent has no such key, so it never
    # reaches the parent (lesson 8.1 showed it missing).
    invoice_id: NotRequired[str]


# endregion


# region billing_nodes
def find_invoice(state: BillingState) -> dict | Command:
    """Pull the invoice number out of the ticket, or hand a tech problem to tech."""
    # The ticket arrived from the desk through the shared `messages` key; the
    # subgraph did not write it. After a handoff from tech the last message
    # is tech's note, not the ticket, so read the ticket with ticket_text.
    text = ticket_text(state["messages"])
    match = re.search(r"INV-\d+", text)
    if match is None and any(word in text.lower() for word in TECH_WORDS):
        # This node does not finish normally: draft_reply never runs, and
        # billing's subgraph never hands its final messages back to the desk
        # (no root billing update with ['human', 'billing'] as in 8.2). Only
        # the handoff's update reaches the desk (section 1 of the run).
        return hand_off(
            "billing", "tech", "Billing team: there is no invoice here, this looks technical."
        )
    return {"invoice_id": match.group() if match else "unknown"}


def draft_reply(state: BillingState) -> dict:
    """Answer the customer about the invoice found in the previous step."""
    text = f"Billing team: the refund for {state['invoice_id']} is on its way."
    # name="billing" says which team wrote the message; the run prints it.
    return {"messages": [AIMessage(text, name="billing")]}


# endregion


# region build_billing
def build_billing() -> CompiledStateGraph:
    """Build and compile the billing subgraph: find_invoice -> draft_reply."""
    builder = StateGraph(BillingState)
    builder.add_node("find_invoice", find_invoice)
    builder.add_node("draft_reply", draft_reply)
    builder.add_edge(START, "find_invoice")
    builder.add_edge("find_invoice", "draft_reply")
    builder.add_edge("draft_reply", END)
    # Compiled with NO checkpointer argument (None, the default). Inside a
    # parent graph it then uses the parent's checkpointer for each run
    # (lesson 8.1). checkpointer=False would opt out of that;
    # checkpointer=True (per-thread memory for the subgraph)
    # is not used in this course's desk.
    return builder.compile()


# endregion

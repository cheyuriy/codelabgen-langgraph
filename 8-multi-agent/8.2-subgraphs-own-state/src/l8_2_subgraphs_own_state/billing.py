"""The billing team as its own small graph; the desk adds it as one node."""

import re
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph


# region billing_state
class BillingState(TypedDict):
    """State of the billing subgraph."""

    # Same name AND same reducer as in DeskState. A key with the same name is
    # the channel parent and subgraph share: the subgraph gets the parent's
    # value as its input and hands its final value back when it finishes.
    messages: Annotated[list[AnyMessage], add_messages]
    # Private to the subgraph: the parent has no such key, so it never
    # reaches the parent (section 1 of the run shows it missing).
    invoice_id: NotRequired[str]


# endregion


# region billing_nodes
def find_invoice(state: BillingState) -> dict:
    """Pull the invoice number out of the customer's ticket."""
    # The last message is the customer's ticket. It arrived from the parent
    # through the shared `messages` key; the subgraph did not write it.
    match = re.search(r"INV-\d+", state["messages"][-1].content)
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
    # (section 4 of the run). checkpointer=False would opt out of that
    # (experiment 2); checkpointer=True (per-thread memory for the subgraph)
    # is not used in this course's desk.
    return builder.compile()


# endregion

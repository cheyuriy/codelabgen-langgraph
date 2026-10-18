"""The two specialist agents, each a create_agent with one tool and its own system prompt.

Nothing here knows about a supervisor: these are plain agents, as in lesson 4.3.
"""

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

# region specialist_tools
# Tiny in-memory "databases" so the run is offline and repeatable.
INVOICES = {"INV-2077": "charged twice (2 x 49.00), one charge refunded on 2026-10-15"}
ORDERS = {"ORD-1042": "shipped 2026-10-14, arrives 2026-10-18"}


@tool
def lookup_invoice(invoice_id: str) -> str:
    """Look up the payment history of an invoice."""
    return INVOICES.get(invoice_id, f"no invoice {invoice_id}")


@tool
def track_order(order_id: str) -> str:
    """Look up where an order is."""
    return ORDERS.get(order_id, f"no order {order_id}")


# endregion

# region specialists
BILLING_PROMPT = "You are the billing specialist."
SHIPPING_PROMPT = "You are the shipping specialist."

# name= does three things in create_agent (langchain/agents/factory.py 1.4.6):
# it becomes the compiled graph's name, it is set as .name on every AIMessage
# the agent's model returns, and it is stored as metadata "lc_agent_name".
# Both agents have nodes "model" and "tools", so the message name is how a
# trace tells billing from shipping.


def build_billing_agent(model: BaseChatModel) -> CompiledStateGraph:
    """The billing specialist: answers invoice and charge questions with lookup_invoice."""
    return create_agent(model, [lookup_invoice], system_prompt=BILLING_PROMPT, name="billing")


def build_shipping_agent(model: BaseChatModel) -> CompiledStateGraph:
    """The shipping specialist: answers order questions with track_order."""
    return create_agent(model, [track_order], system_prompt=SHIPPING_PROMPT, name="shipping")


# endregion

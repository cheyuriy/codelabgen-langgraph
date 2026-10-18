"""The scripted replies of the three fake models and the two customer questions.

Every function returns a FRESH list, because the fake model mutates the
scripted messages (it sets their ids). A real model would read the question
and the tool results; the scripts only stand in for those decisions, the
graph mechanics are real.
"""

from langchain_core.messages import AIMessage

from l8_4_supervisor_agents.fake_model import tool_call

# region scripts
SHIPPING_QUESTION = "Where is my order ORD-1042?"
TWO_PART_QUESTION = "I was charged twice for INV-2077. And where is my order ORD-1042?"


def billing_script() -> list[AIMessage]:
    """The billing specialist: look up the invoice, then answer."""
    return [
        tool_call("lookup_invoice", "bill_1", invoice_id="INV-2077"),
        AIMessage("INV-2077 was charged twice; the extra 49.00 was refunded on 2026-10-15."),
    ]


def shipping_script() -> list[AIMessage]:
    """The shipping specialist: track the order, then answer."""
    return [
        tool_call("track_order", "ship_1", order_id="ORD-1042"),
        AIMessage("ORD-1042 shipped on 2026-10-14 and arrives on 2026-10-18."),
    ]


def supervisor_one_script() -> list[AIMessage]:
    """The supervisor for one question: ask shipping, then answer the customer."""
    return [
        tool_call(
            "ask_shipping", "call_1", request="Where is order ORD-1042 and when will it arrive?"
        ),
        AIMessage("Your order ORD-1042 shipped on 2026-10-14 and arrives on 2026-10-18."),
    ]


def supervisor_two_script() -> list[AIMessage]:
    """The supervisor for the two-part question: both specialists in ONE reply, then answer."""
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "ask_billing",
                    "args": {"request": "Why was INV-2077 charged twice?"},
                    "id": "call_1",
                },
                {
                    "name": "ask_shipping",
                    "args": {"request": "Where is order ORD-1042?"},
                    "id": "call_2",
                },
            ],
        ),
        AIMessage(
            "The second charge of 49.00 on INV-2077 was refunded on 2026-10-15, "
            "and your order ORD-1042 arrives on 2026-10-18."
        ),
    ]


# endregion

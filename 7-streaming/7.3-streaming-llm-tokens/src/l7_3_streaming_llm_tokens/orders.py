"""An order goes through pick, pack, ship and confirm: the graph module 7 streams.

The graph is deliberately tiny and linear, so the stream output is easy to
read. Every lesson in module 7 streams this same order through it.
"""

from typing import NotRequired, TypedDict

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langgraph.config import get_stream_writer
from langgraph.constants import TAG_NOSTREAM
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime


# region order_state
class OrderState(TypedDict):
    """The state of one order.

    The input holds only `order_id` and `items`; the nodes fill in the rest,
    which is why those keys are `NotRequired`.
    """

    order_id: str
    items: list[str]  # SKUs, e.g. ["PEN", "NOTEBOOK"]
    status: NotRequired[str]
    box: NotRequired[str]
    tracking: NotRequired[str]
    email: NotRequired[str]  # written by confirm, streamed token by token
    sms: NotRequired[str]  # written by confirm, streamed token by token
    note: NotRequired[str]  # written by confirm, never streamed


# endregion


# region nodes
# Each node returns ONLY the keys it changes, not the whole state. LangGraph
# merges that partial dict into the state. This is exactly what makes the two
# stream modes differ: "updates" shows these partial dicts as they are,
# "values" shows the full state after they were merged.
def pick(state: OrderState) -> dict:
    """Pick the items from the shelves."""
    return {"status": "picked"}


def pack(state: OrderState) -> dict:
    """Pack the items one by one, reporting progress after each item."""
    # get_stream_writer() returns the writer of the CURRENT run: it reads it
    # from the run's context, so call it inside the node while the run
    # executes it, never at import time (outside a run it raises RuntimeError).
    writer = get_stream_writer()
    total = len(state["items"])
    for done, sku in enumerate(state["items"], start=1):
        # The writer is a plain callable: writer(data). data can be any value;
        # a dict is the convention. It goes to the stream at once, not when the
        # node returns, and it does NOT go into the state.
        # Build a fresh dict for every call: the writer does not copy what you
        # pass, so reusing and mutating one dict would change what the caller sees.
        writer({"node": "pack", "item": sku, "done": done, "total": total})
    return {"status": "packed", "box": "small" if total <= 2 else "large"}


def ship(state: OrderState, runtime: Runtime) -> dict:
    """Hand the parcel to the carrier, report the label, record tracking."""
    # The second way to get the same writer: LangGraph sees the
    # `runtime: Runtime` parameter and injects the run's Runtime (lesson 2.4).
    # Its stream_writer field is the writer get_stream_writer() would return.
    # Because it arrives as an argument, ship can be called in a test with a
    # hand-made Runtime (lesson 7.2, section d).
    tracking = f"TRK-{state['order_id']}"
    runtime.stream_writer({"node": "ship", "label": tracking})
    return {"status": "shipped", "tracking": tracking}


# endregion


# region chat_model
# In a real app this would be init_chat_model("...", tags=...), created once at
# module level. The fake model replies with the scripted text whatever the
# prompt says, and it can answer only once (it reads its replies from an
# iterator), so confirm builds a fresh one for every call.
def chat_model(reply: str, tags: list[str]) -> GenericFakeChatModel:
    """A stand-in for a real chat model that streams `reply` word by word."""
    # `tags` is a standard field of every LangChain chat model. The tags of a
    # call end up in the metadata of each of its tokens, which is how the
    # caller tells the calls apart.
    return GenericFakeChatModel(messages=iter([reply]), tags=tags)


# endregion


# region confirm
def confirm(state: OrderState) -> dict:
    """Write the customer email, the SMS and the warehouse note with a chat model."""
    order, tracking = state["order_id"], state["tracking"]
    # The node calls .invoke(), not .stream(), and still streams: when the
    # caller asks for stream_mode="messages", LangGraph attaches a streaming
    # callback handler to the run, so the model streams under the hood and
    # every token is forwarded to the caller. The node still gets the complete
    # AIMessage back. Without "messages" the same invoke() returns the whole
    # reply in one go.
    email = chat_model(f"Order {order} shipped. Tracking {tracking}.", tags=["email"]).invoke(
        f"Write a one-line shipping email for order {order}, tracking {tracking}."
    )
    sms = chat_model(f"Shipped: {tracking}", tags=["sms"]).invoke(
        f"Write a two-word shipping SMS with tracking {tracking}."
    )
    # TAG_NOSTREAM ("nostream") keeps this call out of the token stream. The
    # call still runs, and its text still goes into the state.
    note = chat_model(f"Box {state['box']} handed to carrier.", tags=[TAG_NOSTREAM]).invoke(
        f"Write a warehouse log line for order {order}."
    )
    # `.text` is the message content as a string (a property in langchain-core
    # 1.x, no parentheses). The state holds plain strings, not messages, so
    # messages mode has no node-output messages to emit here.
    return {"email": email.text, "sms": sms.text, "note": note.text}


# endregion


# region build_graph
def build_graph() -> CompiledStateGraph:
    """Build the linear order graph: START -> pick -> pack -> ship -> confirm -> END."""
    builder = StateGraph(OrderState)
    builder.add_node("pick", pick)
    builder.add_node("pack", pack)
    builder.add_node("ship", ship)
    builder.add_node("confirm", confirm)
    # Each node runs in its own super-step; messages mode yields only while confirm runs.
    builder.add_edge(START, "pick")
    builder.add_edge("pick", "pack")
    builder.add_edge("pack", "ship")
    builder.add_edge("ship", "confirm")
    builder.add_edge("confirm", END)
    return builder.compile()


# endregion

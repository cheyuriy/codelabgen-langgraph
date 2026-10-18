"""The caller's side: plain HTTP through langgraph_sdk.

Nothing from langgraph itself is imported here.
"""

from typing import Any

from langgraph_sdk.client import SyncLangGraphClient

# region assistant
# The graph id from langgraph.json. The server made an assistant with this
# name and accepts the graph id wherever an assistant_id is expected.
ASSISTANT = "support_desk"
# endregion


# region ticket_input
def ticket(text: str) -> dict[str, Any]:
    """Turn a ticket text into the graph's input, as JSON-friendly data."""
    # Input travels as JSON, so messages are dicts, not HumanMessage objects.
    # add_messages in DeskState turns them into messages on the server (the
    # same dict works in-process; the tests use that).
    return {"messages": [{"role": "user", "content": text}]}


# endregion


# region ask
def ask(client: SyncLangGraphClient, thread_id: str, text: str) -> dict[str, Any]:
    """Run the support desk on the thread with one ticket and return the final state."""
    # runs.wait creates a run on the thread, blocks until it finishes and
    # returns the thread's final state values (a dict; messages come back as
    # dicts with "type", "name", "content"). If the graph raises, this call
    # does not: the dict is {"__error__": {"error": ..., "message": ...}}
    # (experiment 2).
    return client.runs.wait(thread_id, ASSISTANT, input=ticket(text))


# endregion


def reply_line(state: dict[str, Any]) -> str:
    """Format the last message of a state as 'name: content'."""
    last = state["messages"][-1]
    return f"{last['name']}: {last['content']}"

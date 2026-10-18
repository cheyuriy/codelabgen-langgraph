"""Small helpers that turn messages and namespaces into short, stable text for printing."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage


# region show_helpers
def label(message: AnyMessage) -> str:
    """Who wrote a message: its name ("supervisor", "billing", ...), else its type."""
    return message.name or message.type


def describe(message: AnyMessage) -> str:
    """One line per message: a tool request, a tool result or plain text (never ids)."""
    if isinstance(message, AIMessage) and message.tool_calls:
        calls = []
        for call in message.tool_calls:
            args = ", ".join(f"{key}={value!r}" for key, value in call["args"].items())
            calls.append(f"{call['name']}({args}) [{call['id']}]")
        return f"{label(message)} asks for " + ", ".join(calls)
    if isinstance(message, ToolMessage):
        return f"ToolMessage [{message.tool_call_id}] {message.name} = {message.content}"
    return f"{label(message)}: {message.content}"


def node_path(ns: Sequence[str]) -> str:
    """Turn a namespace into node names only, such as "tools" or "(root)"."""
    # A namespace is a tuple of "node_name:<task_id>" strings, one per level,
    # and () for the parent graph. The task id in "tools:<uuid>" changes on
    # every run, so print only the node names.
    return "/".join(part.split(":")[0] for part in ns) or "(root)"


# endregion

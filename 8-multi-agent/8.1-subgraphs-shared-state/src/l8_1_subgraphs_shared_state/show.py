"""Small helpers that turn messages, namespaces and updates into short, stable text for printing."""

from collections.abc import Sequence

from langchain_core.messages import AnyMessage


# region show_helpers
def label(message: AnyMessage) -> str:
    """Who wrote a message: its name, else its type ("human" for the ticket)."""
    return message.name or message.type


def node_path(ns: Sequence[str]) -> str:
    """Turn a namespace into node names only, such as "billing" or "(root)"."""
    # A namespace is a tuple of "node_name:<task_id>" strings, one per level,
    # and () for the parent graph. The task id is a fresh uuid on every run,
    # so print only the node names. The same function reads a checkpoint_ns
    # string, whose levels are joined with "|", after checkpoint_ns.split("|")
    # ("" gives [""], which also prints "(root)").
    return "/".join(part.split(":")[0] for part in ns) or "(root)"


def brief(update: dict) -> dict:
    """Shorten an update for printing: messages become their labels."""
    return {
        key: [label(m) for m in value] if key == "messages" else value
        for key, value in update.items()
    }


# endregion

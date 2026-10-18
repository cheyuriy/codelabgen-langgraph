"""Scripted, offline chat models for all three agents (supervisor, billing, shipping).

The fake ignores its input and returns the next scripted reply. The graph
mechanics around it (tool calls, ToolNode, subgraph runs) are all real.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


# region fake_model
class ToolCallingFakeModel(GenericFakeChatModel):
    """A GenericFakeChatModel that create_agent can use.

    It ignores the messages it gets and returns the next scripted reply. The
    script is an iterator, consumed once: build a fresh model (and agent) per
    run. A specialist called twice in one run with a two-reply script fails
    with "RuntimeError: generator raised StopIteration".
    """

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ToolCallingFakeModel":
        """Accept the tools and return the model unchanged.

        create_agent calls bind_tools before every model call, and
        GenericFakeChatModel's own bind_tools raises NotImplementedError in
        langchain-core 1.6.12. The scripted replies already name the tools.
        """
        return self


def make_model(replies: Iterable[AIMessage]) -> ToolCallingFakeModel:
    """Build a fake model that returns `replies` one per call.

    The fake sets ids on the scripted AIMessage objects themselves, so never
    share one script list between two models: build a fresh list per model.
    """
    return ToolCallingFakeModel(messages=iter(replies))


def tool_call(name: str, call_id: str, **args: str) -> AIMessage:
    """A scripted reply that asks for one tool call, like a real model would."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


# endregion

"""The to-do agent loop: START -> call_model -> (tools -> call_model)* -> END.

Built as in 4.2, but compiled with a checkpointer, because a tool that calls
interrupt() needs one to pause and resume the run.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

# ToolNode and tools_condition live in the langgraph-prebuilt package (1.1.1),
# imported as langgraph.prebuilt. They work with langchain_core tools.
from langgraph.prebuilt import ToolNode, tools_condition

from l6_4_interrupts_in_tools.todos import TOOLS


# region fake_model
class ToolCallingFakeModel(GenericFakeChatModel):
    """A scripted chat model that accepts bind_tools.

    GenericFakeChatModel.bind_tools raises NotImplementedError in
    langchain-core 1.6.12. A real model would send the tool schemas to the
    provider; this fake ignores them because its replies are scripted.
    """

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ToolCallingFakeModel":
        """Return the model itself: the scripted replies already say which tools to call."""
        return self


def make_model(replies: Iterable[AIMessage | str]) -> ToolCallingFakeModel:
    """Build an offline chat model that answers with the scripted replies, in order.

    The replies are consumed in order across ALL invokes of the thread, the
    pause and the resume included. Calling the model after the script is used
    up raises ``StopIteration`` (inside a graph run:
    ``RuntimeError: generator raised StopIteration``). The fake mutates the
    AIMessage objects it returns (it sets their ids), so build a fresh script
    per model.
    """
    return ToolCallingFakeModel(messages=iter(replies))


def asks_for(*calls: tuple[str, str, dict[str, Any]]) -> AIMessage:
    """Build a model reply asking for one or more tool calls.

    Each call is given as (tool name, call id, arguments). Several calls in
    one reply are what a real model sends for parallel tool calls.
    """
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id} for name, call_id, args in calls],
    )


# endregion


# region build_agent
def build_agent(
    model: BaseChatModel, checkpointer: BaseCheckpointSaver | None
) -> CompiledStateGraph:
    """Compile the to-do agent loop with the given checkpointer.

    The graph is 4.2's loop unchanged: nothing in the wiring knows about
    approval. The pause comes from inside delete_task.
    """
    # Tell the model which tools exist, once. The fake returns itself.
    model_with_tools = model.bind_tools(TOOLS)

    def call_model(state: MessagesState) -> dict:
        """Send the conversation to the model and return only its reply."""
        # No system prompt: the scripted fake does not need one.
        return {"messages": [model_with_tools.invoke(state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    # ToolNode runs ALL tool calls of the last AIMessage inside ONE task (in a
    # thread pool). If one of them pauses, none of their ToolMessages is saved,
    # and on resume the whole node, every call of that reply, runs again.
    # The node must be named "tools": that is the name tools_condition returns.
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "call_model")
    # "tools" if the last message has tool calls, otherwise END.
    builder.add_conditional_edges("call_model", tools_condition)
    builder.add_edge("tools", "call_model")
    # The checkpointer makes the pause resumable (6.1): the saved checkpoint
    # holds the conversation up to the AIMessage with the tool call and marks
    # the "tools" task as pending. call_model is not re-run on resume: its
    # reply is already in the checkpoint.
    return builder.compile(checkpointer=checkpointer)


# endregion

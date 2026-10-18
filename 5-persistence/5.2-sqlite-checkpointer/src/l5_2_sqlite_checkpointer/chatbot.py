"""The calculator agent from lesson 4.2, plus a checkpointer.

Wiring: START -> call_model -> (tools -> call_model)* -> END, unchanged from
4.2. The model is an offline, scripted fake whose replies decide which tools
run. What is new: build_graph takes a checkpointer, so the graph remembers each
conversation (thread) between invokes.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, SystemMessage

# BaseCheckpointSaver is the interface every checkpointer implements
# (InMemorySaver here, SqliteSaver in 5.2, PostgresSaver in 5.6).
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

# ToolNode and tools_condition live in the langgraph-prebuilt package (1.1.1),
# imported as langgraph.prebuilt. Their docstrings mention langchain.tools,
# which is not installed here; they work with langchain_core tools.
from langgraph.prebuilt import ToolNode, tools_condition

from l5_2_sqlite_checkpointer.tools import TOOLS

# region system_prompt
# The instruction for the model. It is prepended on every call, never stored in state.
SYSTEM_PROMPT = "You are a helpful assistant tasked with performing arithmetic on a set of inputs."
# endregion


# region fake_model
class ToolCallingFakeModel(GenericFakeChatModel):
    """A scripted chat model that accepts bind_tools.

    GenericFakeChatModel.bind_tools raises NotImplementedError in
    langchain-core 1.6.12. A real model would send the tool schemas to the
    provider; this fake ignores them because its replies are scripted. Same
    pattern as FakeChatModel in langgraph's own libs/langgraph/tests/fake_chat.py.
    """

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ToolCallingFakeModel":
        """Return the model itself: the scripted replies already say which tools to call."""
        return self


def make_model(replies: Iterable[AIMessage | str]) -> ToolCallingFakeModel:
    """Build an offline chat model that answers with the scripted replies, in order.

    The model ignores its input and returns the next reply from the iterator
    (any iterable works, including an endless generator). The iterator is
    consumed once, so build a fresh model per run or test. Calling it after the
    script is used up raises ``StopIteration``. Inside a graph run, that
    surfaces as ``RuntimeError: generator raised StopIteration`` (langgraph
    1.2.16 behaviour). One model serves every invoke of the graph, so a
    multi-turn run needs one script with the replies of all turns, in call
    order.

    The fake sets an id on each scripted AIMessage object it returns (it
    mutates the object). So build the script fresh per model and never put the
    same AIMessage object in a script twice: with a repeated object,
    add_messages sees an existing id, replaces the earlier message in place,
    and tools_condition then sees a ToolMessage last and ends the run early.
    """
    return ToolCallingFakeModel(messages=iter(replies))


def tool_call(name: str, call_id: str, **args: int) -> AIMessage:
    """Build a model reply that asks for one tool call.

    This is what a real model returns when it wants a tool: empty content and
    a ``tool_calls`` entry with the tool name, its arguments and a call id.
    langchain-core adds ``"type": "tool_call"`` to each entry.
    """
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


# endregion


# region build_graph
def build_graph(
    model: BaseChatModel, checkpointer: BaseCheckpointSaver | None
) -> CompiledStateGraph:
    """Compile the agent loop START -> call_model -> (tools -> call_model)* -> END.

    call_model asks the model; if its reply has tool calls, tools_condition
    routes to the "tools" node, which runs them and loops back to call_model.
    A reply without tool calls routes to END. With a checkpointer, the graph
    saves its state after every super-step under the thread_id of the run's
    config, and the next invoke on that thread continues from it. With
    ``None`` the graph forgets everything between invokes, as in 4.2.
    """
    # Tell the model which tools exist, once. A real model now includes their
    # schemas in every request; the fake returns itself.
    model_with_tools = model.bind_tools(TOOLS)

    # region call_model
    def call_model(state: MessagesState) -> dict:
        """Send the conversation to the model and return only its reply."""
        # The system message is built for this call only; it is NOT stored in state.
        reply = model_with_tools.invoke([SystemMessage(SYSTEM_PROMPT)] + state["messages"])
        # Return just the new message: the add_messages reducer on
        # MessagesState appends it to the existing history.
        return {"messages": [reply]}

    # endregion

    # MessagesState has one key, "messages", reduced by add_messages.
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    # ToolNode runs every tool call of the last AIMessage and returns one
    # ToolMessage per call, with tool_call_id set to the call's id. The node
    # must be named "tools": that is the name tools_condition returns.
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "call_model")
    # tools_condition returns "tools" if the last message has tool calls,
    # otherwise "__end__" (END). This replaces 4.1's call_model -> END edge.
    builder.add_conditional_edges("call_model", tools_condition)
    # The back edge makes it a loop (ReAct): act, observe, think again.
    builder.add_edge("tools", "call_model")
    # The only change from 4.2. The checkpointer saves the whole state after
    # every super-step, keyed by the thread_id in config["configurable"].
    # Every invoke on the same thread starts from that thread's latest
    # checkpoint, so its input is added to the saved history. None compiles
    # without persistence, as in 4.2.
    return builder.compile(checkpointer=checkpointer)


# endregion

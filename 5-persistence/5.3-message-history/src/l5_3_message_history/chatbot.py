"""The calculator agent from lesson 5.2, with a bounded history.

The model sees only the most recent messages, and once a finished turn leaves
too many messages in the saved state, the old ones are folded into a running
summary and deleted from the state. The models are offline, scripted fakes.

Wiring: START -> call_model -> (tools -> call_model)* -> [summarize] -> END.
"""

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    trim_messages,
)

# BaseCheckpointSaver is the interface every checkpointer implements
# (InMemorySaver in the tests, SqliteSaver in the run, PostgresSaver in 5.6).
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

# ToolNode and tools_condition live in the langgraph-prebuilt package (1.1.1),
# imported as langgraph.prebuilt. Their docstrings mention langchain.tools,
# which is not installed here; they work with langchain_core tools.
from langgraph.prebuilt import ToolNode, tools_condition

from l5_3_message_history.tools import TOOLS

# region system_prompt
# The instruction for the model. It is prepended on every call, never stored in state.
SYSTEM_PROMPT = "You are a helpful assistant tasked with performing arithmetic on a set of inputs."
# endregion

# region history_limits
# The limits are counted in messages (token_counter=len below), so the numbers
# are easy to follow. A real app counts tokens instead, for example with
# token_counter="approximate" (langchain_core.messages.utils
# .count_tokens_approximately) or with the chat model itself, and sets
# max_tokens to a budget below the model's context window.
MAX_MODEL_MESSAGES = 5  # how many saved messages the model sees at most
SUMMARIZE_AFTER = 6  # summarize once a finished turn leaves more than this
KEEP_AFTER_SUMMARY = 4  # how many recent messages survive a summary at most
SUMMARY_PREFIX = "Summary of the earlier conversation:"
# endregion


# region state
class State(MessagesState):
    """The agent's state: messages plus a running summary.

    ``messages`` comes from MessagesState and is reduced by add_messages.
    ``summary`` holds a summary of the messages already deleted from the
    state. It has no reducer, so a node's update replaces it. It is missing
    until the first summary is written, so read it with
    ``state.get("summary", "")``.
    """

    summary: str


# endregion


# region recent_messages
def recent_messages(messages: Sequence[BaseMessage], max_messages: int) -> list[BaseMessage]:
    """Return the newest messages, at most ``max_messages``, starting at a turn boundary.

    trim_messages returns a new list holding the same message objects; it
    never changes its input. The window can be shorter than ``max_messages``,
    and it is empty if it contains no HumanMessage.
    """
    return trim_messages(
        messages,
        # Keep the newest messages and drop the oldest.
        strategy="last",
        # Count every message as 1 "token", so max_tokens is a message count.
        token_counter=len,
        max_tokens=max_messages,
        # Then drop messages from the front of that window until it starts
        # with a HumanMessage. This keeps tool calls and their ToolMessages
        # together (the pairing rule from 4.2): without it, a window of 5 can
        # start with a ToolMessage whose AIMessage tool call was cut off, which
        # real providers reject. The cost: fewer messages than allowed.
        start_on="human",
        # No end_on here: in the middle of a turn the last message is a
        # ToolMessage the model must see. include_system is not needed either:
        # the system message is never stored in state.
    )


# endregion


# region model_input
def model_input(state: State) -> list[BaseMessage]:
    """Build exactly what call_model sends: system prompt (+ summary) + recent messages.

    The summary rides in the system prompt, so the model still knows what the
    deleted messages said.
    """
    system = SYSTEM_PROMPT
    summary = state.get("summary", "")
    if summary:
        system += f"\n\n{SUMMARY_PREFIX} {summary}"
    # This only shapes the request; the saved state is untouched.
    return [SystemMessage(system)] + recent_messages(state["messages"], MAX_MODEL_MESSAGES)


# endregion


# region route_after_model
def route_after_model(state: State) -> Literal["tools", "summarize", "__end__"]:
    """Pick the next node after call_model: tools, summarize or END.

    This replaces tools_condition as the edge out of call_model.
    """
    # A reply with tool calls goes to the tools node, exactly as before.
    if tools_condition(state) == "tools":
        return "tools"
    # A reply without tool calls ends the turn, and only then is the history
    # checked. So a summary never runs between a tool call and its result: the
    # last message is a final AIMessage and the state ends on a complete turn.
    # Below the threshold the turn ends as before.
    return "summarize" if len(state["messages"]) > SUMMARIZE_AFTER else END


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
    model: BaseChatModel, checkpointer: BaseCheckpointSaver | None, summarizer: BaseChatModel
) -> CompiledStateGraph:
    """Compile START -> call_model -> (tools -> call_model)* -> [summarize] -> END.

    call_model asks the model; if its reply has tool calls, route_after_model
    routes to the "tools" node, which runs them and loops back to call_model.
    A reply without tool calls ends the turn: it routes to "summarize" when
    the saved history is longer than SUMMARIZE_AFTER, otherwise to END.
    ``summarizer`` is a chat model used only to write summaries; any chat
    model works, the run uses a second scripted fake. With a checkpointer, the
    graph saves its state after every super-step under the thread_id of the
    run's config, and the next invoke on that thread continues from it. With
    ``None`` the graph forgets everything between invokes, as in 4.2.
    """
    # Tell the model which tools exist, once. A real model now includes their
    # schemas in every request; the fake returns itself.
    model_with_tools = model.bind_tools(TOOLS)

    # region call_model
    def call_model(state: State) -> dict:
        """Send the conversation to the model and return only its reply."""
        # The request is built by model_input (system prompt + summary +
        # trimmed recent messages); the state keeps every message.
        reply = model_with_tools.invoke(model_input(state))
        # Return just the new message: the add_messages reducer on
        # MessagesState appends it to the existing history.
        return {"messages": [reply]}

    # endregion

    # region summarize_history
    def summarize(state: State) -> dict:
        """Fold the old messages into the running summary and delete them from state."""
        # The kept part is chosen with the same recent_messages, so it starts
        # with a HumanMessage and the deleted part is a prefix of complete
        # turns: no ToolMessage loses its tool call.
        kept = recent_messages(state["messages"], KEEP_AFTER_SUMMARY)
        # A turn longer than KEEP_AFTER_SUMMARY (say, two tool calls: human ai
        # tool tool ai) leaves no HumanMessage in the window, so kept is empty
        # and every message, the latest answer included, would be deleted.
        # Skip the summary this turn instead; a later turn that fits summarizes.
        # Size the limits for the longest turn you expect.
        if not kept:
            return {}
        kept_ids = {m.id for m in kept}
        old = [m for m in state["messages"] if m.id not in kept_ids]
        # The summarizer reads only the messages about to be deleted plus the
        # previous summary, so the summary is running: each run extends it
        # instead of re-reading the whole history.
        summary = state.get("summary", "")
        if summary:
            instruction = (
                f"This is the summary so far: {summary}\nExtend it with the new messages above."
            )
        else:
            instruction = "Summarize the conversation above."
        reply = summarizer.invoke(old + [HumanMessage(instruction)])
        # A node cannot shrink the list by returning a shorter one: add_messages
        # would merge it into the history. Instead it returns RemoveMessage
        # entries, and add_messages deletes the messages with those ids. Every
        # message in state has an id (add_messages assigns a uuid to messages
        # without one), and the id must exist, otherwise add_messages raises
        # ValueError. The deletion is a normal state update, so the
        # checkpointer saves the smaller state as the thread's latest
        # checkpoint; earlier checkpoints still contain the deleted messages.
        # add_messages also supports RemoveMessage(id=REMOVE_ALL_MESSAGES)
        # (from langgraph.graph.message) to clear the whole list, but open
        # issue #9326 (reproduced on 1.2.16): messages after it are returned
        # without id merging, so duplicate ids survive. This lesson deletes by id.
        return {"summary": reply.content, "messages": [RemoveMessage(id=m.id) for m in old]}

    # endregion

    # State is MessagesState ("messages", reduced by add_messages) plus "summary".
    builder = StateGraph(State)
    builder.add_node("call_model", call_model)
    # ToolNode runs every tool call of the last AIMessage and returns one
    # ToolMessage per call, with tool_call_id set to the call's id. The node
    # must be named "tools": that is the name tools_condition returns.
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_node("summarize", summarize)
    builder.add_edge(START, "call_model")
    # route_after_model returns "tools" if the last message has tool calls,
    # otherwise "summarize" past the threshold, or "__end__" (END). It
    # replaces tools_condition from 4.2 and 5.2.
    builder.add_conditional_edges("call_model", route_after_model)
    # The back edge makes it a loop (ReAct): act, observe, think again.
    builder.add_edge("tools", "call_model")
    # A summary always ends the turn.
    builder.add_edge("summarize", END)
    # Unchanged from 5.2. The checkpointer saves the whole state after
    # every super-step, keyed by the thread_id in config["configurable"].
    # Every invoke on the same thread starts from that thread's latest
    # checkpoint, so its input is added to the saved history. None compiles
    # without persistence, as in 4.2.
    return builder.compile(checkpointer=checkpointer)


# endregion

"""A one-node calculator chatbot: MessagesState plus an offline, scripted chat model."""

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

# region system_prompt
# The instruction for the model. It is prepended on every call, never stored in state.
SYSTEM_PROMPT = "You are a helpful assistant tasked with performing arithmetic on a set of inputs."
# endregion


# region fake_model
def make_model(replies: list[str]) -> GenericFakeChatModel:
    """Build an offline chat model that answers with the scripted replies, in order.

    The model ignores its input and returns the next reply from the iterator.
    ``messages`` must be an iterator: a plain list fails pydantic validation
    ("Input should be an instance of Iterator"). The iterator is consumed once,
    so build a fresh model per run or test. Calling it after the script is used up raises
    ``StopIteration``. Inside a graph run, that surfaces as ``RuntimeError: generator raised
    StopIteration`` (langgraph 1.2.16 behaviour).
    """
    return GenericFakeChatModel(messages=iter(replies))


# endregion


# region build_graph
def build_graph(model: BaseChatModel) -> CompiledStateGraph:
    """Compile a graph START -> call_model -> END over the built-in MessagesState.

    There is no checkpointer, so the graph forgets everything between invokes:
    the caller carries the history by passing the previous messages back in.
    """

    # region call_model
    def call_model(state: MessagesState) -> dict:
        """Send the conversation to the model and return only its reply."""
        # The system message is built for this call only; it is NOT stored in state.
        reply = model.invoke([SystemMessage(SYSTEM_PROMPT)] + state["messages"])
        # Return just the new message: the add_messages reducer on
        # MessagesState appends it to the existing history.
        return {"messages": [reply]}

    # endregion

    # MessagesState has one key, "messages", reduced by add_messages.
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)
    return builder.compile()


# endregion

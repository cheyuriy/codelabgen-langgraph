"""The calculator agent built by langchain's create_agent.

Same tools, same model and same system prompt as chatbot.build_graph, but the
graph is assembled by one library call instead of by hand.
"""

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from l4_3_create_agent.chatbot import SYSTEM_PROMPT
from l4_3_create_agent.tools import TOOLS

# The old way (do NOT use it; shown only so you recognise it in older code):
#   from langgraph.prebuilt import create_react_agent
#   create_react_agent(model, TOOLS, prompt=SYSTEM_PROMPT)   # node "agent"
# It is deprecated since LangGraph 1.0 and warns with LangGraphDeprecatedSinceV10:
# "create_react_agent has been moved to `langchain.agents`. Please update your
# import to `from langchain.agents import create_agent`." It will be removed in
# V2.0. create_agent has no prompt parameter: it is called system_prompt now,
# and the model node is named "model" instead of "agent".


# region build_agent
def build_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Compile the calculator agent with create_agent (langchain 1.4.6).

    create_agent builds a StateGraph with a node "model" that calls the model
    and, because tools were given, a node "tools" that is a ToolNode from
    langgraph.prebuilt, and compiles it: the same loop as build_graph.

    The state schema is langchain's AgentState: "messages" plus
    "structured_response" (only filled when response_format is given) and a
    private "jump_to" key used by middleware.
    """
    # What happens inside, per run:
    # - The "model" node calls model.bind_tools(tools, tool_choice=None) on
    #   EVERY model call (build_graph binds once), then invokes the result with
    #   [SystemMessage(system_prompt), *state messages]. 4.2's fake model
    #   returns itself from bind_tools, so it works unchanged. The system
    #   prompt is prepended per call and never stored in state.
    # - The routing after "model" is create_agent's own conditional edge, not
    #   tools_condition: no tool calls -> END; otherwise one Send("tools",
    #   [tool_call]) per pending call, so each call runs as its own task in
    #   the same super-step. The edge tools -> model is conditional too: it
    #   can exit early for tools declared with return_direct=True.
    # - The compiled graph carries a default config recursion_limit of 9999
    #   (via .with_config); a recursion_limit passed to invoke/stream wins.
    #
    # Other keyword arguments are the extension points (not used here):
    #   middleware=[...]     hooks before/after the model and around tool
    #                        calls; each becomes graph nodes or wrappers
    #   response_format=...  structured output into "structured_response"
    #   state_schema=, context_schema=   extra state keys, run-time context
    #   checkpointer=, store=            memory (module 5)
    #   interrupt_before=, interrupt_after=, name=
    return create_agent(model, TOOLS, system_prompt=SYSTEM_PROMPT)


# endregion


# region inspect_graph
def edges(graph: CompiledStateGraph) -> list[str]:
    """List a compiled graph's edges as sorted "source --> target" strings.

    Works on any compiled graph, the prebuilt agent and the hand-built one
    alike. "-.->" marks a conditional edge, as in the Mermaid drawing;
    "-->" is a fixed edge.
    """
    return sorted(
        f"{e.source} {'-.->' if e.conditional else '-->'} {e.target}"
        for e in graph.get_graph().edges
    )


# endregion

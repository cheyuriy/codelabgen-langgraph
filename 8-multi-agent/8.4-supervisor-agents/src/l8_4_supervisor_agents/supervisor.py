"""The supervisor agent, whose tools are other agents."""

from langchain.agents import create_agent
from langchain.tools import BaseTool, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph


# region agent_as_tool
def as_tool(agent: CompiledStateGraph, name: str, description: str) -> BaseTool:
    """Wrap a compiled agent as a tool that takes one request string."""

    # The tool is the whole contract between the two levels. The supervisor's
    # model only sees the name, the description and one argument, `request`.
    @tool(name, description=description)
    def ask(request: str) -> str:
        """Run the specialist on the request and return its final answer."""
        # The supervisor's model wrote `request` as a tool-call argument. The
        # specialist starts a FRESH conversation with only that HumanMessage:
        # it never sees the customer's message or the supervisor's history
        # (context isolation).
        #
        # No config is passed, yet this run is still a child of the
        # supervisor's run: LangGraph hands the parent config down through a
        # context variable, so stream(subgraphs=True) on the supervisor shows
        # the specialist's steps under the namespace "tools:<task id>".
        #
        # The specialist has no checkpointer: every call is a new, stateless run.
        result = agent.invoke({"messages": [HumanMessage(request)]})
        # Only the final message's content travels back. create_agent's
        # ToolNode wraps it in the ToolMessage for this call; the specialist's
        # own tool calls stay inside its run.
        return result["messages"][-1].content

    return ask


# endregion

# region build_supervisor
SUPERVISOR_PROMPT = (
    "You are the support supervisor. Ask the billing specialist about invoices "
    "and charges and the shipping specialist about orders, then answer the customer."
)


def build_supervisor(
    model: BaseChatModel, billing: CompiledStateGraph, shipping: CompiledStateGraph
) -> CompiledStateGraph:
    """The supervisor agent: two specialists as its tools, and the last word to the customer."""
    # To the supervisor these are ordinary tools, like 4.3's add and multiply.
    # create_agent sends every tool call of one reply to its own "tools" task
    # (Send), so two specialist calls in one reply run in the same super-step.
    # After every tools step control returns to the supervisor's model node:
    # the supervisor, not a specialist, decides what happens next and writes
    # the reply to the customer.
    return create_agent(
        model,
        [
            as_tool(
                billing,
                "ask_billing",
                "Ask the billing specialist about an invoice, a charge or a refund.",
            ),
            as_tool(
                shipping,
                "ask_shipping",
                "Ask the shipping specialist where an order is and when it arrives.",
            ),
        ],
        system_prompt=SUPERVISOR_PROMPT,
        name="supervisor",
    )


# endregion

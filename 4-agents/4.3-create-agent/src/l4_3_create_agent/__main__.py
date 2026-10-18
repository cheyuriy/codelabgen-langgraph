"""Live run: create_agent next to the hand-built graph, what it compiles to, and two tool calls."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage

from l4_3_create_agent.agent import build_agent, edges
from l4_3_create_agent.chatbot import (
    build_graph,
    make_model,
    tool_call,
    unanswered_tool_calls,
)


def describe(m: AnyMessage) -> str:
    """Return a one-line description of a message (never its id: ids change per run)."""
    if isinstance(m, AIMessage) and m.tool_calls:
        calls = []
        for tc in m.tool_calls:
            args = ", ".join(f"{k}={v}" for k, v in tc["args"].items())
            calls.append(f"{tc['name']}({args}) [{tc['id']}]")
        return "AIMessage asks for " + ", ".join(calls)
    if isinstance(m, ToolMessage):
        return f"ToolMessage [{m.tool_call_id}] {m.name} = {m.content}"
    return f"{type(m).__name__}: {m.content}"


def script() -> list[AIMessage]:
    """Return the scripted model replies for (3 + 4) * 2 / 7, as a FRESH list.

    The fake model sets ids on the message objects it returns, so two models
    must never share one list.
    """
    return [
        tool_call("add", "call_1", a=3, b=4),
        tool_call("multiply", "call_2", a=7, b=2),
        tool_call("divide", "call_3", a=14, b=7),
        AIMessage("(3 + 4) * 2 / 7 is 2.0."),
    ]


def main() -> None:
    """Run the three sections of the lesson."""
    # region same_loop
    print("== create_agent runs the same loop ==")
    agent = build_agent(make_model(script()))
    question = "What is (3 + 4) * 2 / 7?"
    print("question:", question)

    agent_nodes: list[str] = []
    for update in agent.stream(
        {"messages": [HumanMessage(question)]},
        {"recursion_limit": 10},
        stream_mode="updates",
    ):
        # "updates" yields {node_name: what_the_node_returned} per step,
        # exactly as for the hand-built graph.
        for node, delta in update.items():
            agent_nodes.append(node)
            for m in delta["messages"]:
                print(f"  {node:<6} {describe(m)}")

    # The hand-built graph from 4.2, run with its own fresh script.
    hand_nodes: list[str] = []
    for update in build_graph(make_model(script())).stream(
        {"messages": [HumanMessage(question)]},
        {"recursion_limit": 10},
        stream_mode="updates",
    ):
        hand_nodes.extend(update)
    # Same super-steps, same messages: only the model node's name differs.
    print("  create_agent: " + " -> ".join(agent_nodes))
    print("  by hand:      " + " -> ".join(hand_nodes))
    # endregion

    # region under_the_hood
    print()
    print("== Underneath: a compiled LangGraph graph ==")
    # Never invoked, so an empty script is fine.
    hand = build_graph(make_model([]))
    # create_agent returns a CompiledStateGraph, so everything from modules
    # 1-3 applies: stream modes, get_graph, recursion_limit, and later
    # checkpointers and interrupts.
    print("type:", type(agent).__name__)
    print("create_agent edges:", edges(agent))
    print("hand-built edges:  ", edges(hand))
    print(
        "output keys:",
        list(agent.get_output_jsonschema()["properties"]),
        "vs",
        list(hand.get_output_jsonschema()["properties"]),
    )
    # The agent's default limit is 9999: a stuck model could loop a long
    # time, so pass your own recursion_limit, as this file does.
    print("default recursion_limit:", agent.config["recursion_limit"])
    # endregion

    # region parallel_calls
    print()
    print("== Two tool calls in one reply ==")
    two_calls = AIMessage(
        content="",
        tool_calls=[
            {"name": "add", "args": {"a": 3, "b": 4}, "id": "call_a"},
            {"name": "multiply", "args": {"a": 5, "b": 6}, "id": "call_b"},
        ],
    )
    agent = build_agent(make_model([two_calls, AIMessage("3 + 4 is 7 and 5 * 6 is 30.")]))
    result = agent.invoke(
        {"messages": [HumanMessage("What are 3 + 4 and 5 * 6?")]},
        {"recursion_limit": 10},
    )
    messages = result["messages"]
    # create_agent sends each call to its own "tools" task (Send); both run
    # in one super-step. The state keeps call order, but the order of the two
    # "tools" updates in a stream is not fixed, so we print the final state.
    for m in messages:
        print(f"  {describe(m)}")
    print("unanswered tool calls:", unanswered_tool_calls(messages))
    print("system messages in state:", sum(isinstance(m, SystemMessage) for m in messages))
    # endregion

    # Module 5 adds memory to this agent with a checkpointer.


if __name__ == "__main__":
    main()

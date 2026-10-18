"""Live run: the agent loop step by step, then one reply with two tool calls."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

from l4_2_tool_calling_loop.chatbot import (
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


def main() -> None:
    """Run both sections of the lesson."""
    # region agent_loop
    print("== The agent loop, step by step ==")
    # Built fresh here: the fake model sets ids on these message objects.
    script = [
        tool_call("add", "call_1", a=3, b=4),
        tool_call("multiply", "call_2", a=7, b=2),
        tool_call("divide", "call_3", a=14, b=7),
        AIMessage("(3 + 4) * 2 / 7 is 2.0."),
    ]
    graph = build_graph(make_model(script))
    question = "What is (3 + 4) * 2 / 7?"
    print("question:", question)

    # Each node run is one super-step; this run takes 7. A run of N steps
    # needs recursion_limit >= N + 1 (lesson 1.3). The default in 1.2.16 is
    # 10007, so set a small limit on agent loops.
    steps = 0
    for update in graph.stream(
        {"messages": [HumanMessage(question)]},
        {"recursion_limit": 10},
        stream_mode="updates",
    ):
        # "updates" yields {node_name: what_the_node_returned} per step.
        for node, delta in update.items():
            steps += 1
            for m in delta["messages"]:
                print(f"  {node:<10} {describe(m)}")
    print(
        f"  {steps} steps; tools_condition found no tool calls in the last reply and routed to END"
    )
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
    graph = build_graph(make_model([two_calls, AIMessage("3 + 4 is 7 and 5 * 6 is 30.")]))
    result = graph.invoke(
        {"messages": [HumanMessage("What are 3 + 4 and 5 * 6?")]},
        {"recursion_limit": 10},
    )
    messages = result["messages"]
    # ToolNode answers every call of the reply, in call order, each
    # ToolMessage carrying the tool_call_id it answers.
    for m in messages:
        print(f"  {describe(m)}")
    print("unanswered tool calls:", unanswered_tool_calls(messages))

    broken = [
        m for m in messages if not (isinstance(m, ToolMessage) and m.tool_call_id == "call_b")
    ]
    # Sent to a real provider, this history is rejected: the model may never
    # see a tool call without its result. The fake does not check, so we do.
    print("after dropping the answer to call_b:", unanswered_tool_calls(broken))
    # endregion


if __name__ == "__main__":
    main()

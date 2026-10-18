"""Live run: draw the ticket graph, invoke it, stream it and hit the recursion limit."""

from langgraph.errors import GraphRecursionError

from l1_3_loops_and_recursion_limit.graph import build_graph

SAMPLE_TICKETS = [
    "I was charged twice, please refund me",  # billing queue, high priority
    "The app shows an error on login",  # tech queue
    "Do you have a dark mode?",  # general queue
]


def main() -> None:
    """Build the graph once and show it at work on a few sample tickets."""
    graph = build_graph()

    # region draw_mermaid
    # get_graph() returns a drawable view of the compiled graph.
    print("== Graph (Mermaid) ==")
    print(graph.get_graph().draw_mermaid())
    # endregion

    # region invoke
    # invoke() runs the graph to the end and returns the final state.
    # We pass only "text"; the nodes fill in clean_text, priority, category,
    # the reply (drafted by a queue node, polished by the loop) and problems.
    print("== invoke() ==")
    for ticket in SAMPLE_TICKETS:
        print(graph.invoke({"text": ticket}))
    # endregion

    # region stream_updates
    # stream_mode="updates" yields one {node_name: partial_update} per step.
    # In this graph every super-step runs exactly one node, so one update is
    # one super-step; the numbers match LangGraph's own langgraph_step.
    print("\n== stream(stream_mode='updates') ==")
    for step, update in enumerate(
        graph.stream({"text": "  Refund   please "}, stream_mode="updates"), start=1
    ):
        print(f"step {step}: {update}")
    # endregion

    # region recursion_limit
    # recursion_limit caps the number of super-steps in one run. The guard in
    # route_after_check turns a too-small limit into an early, graceful stop,
    # but it cannot help if the limit is too small to even reach the loop:
    # then LangGraph raises GraphRecursionError.
    print("\n== recursion_limit ==")
    for limit in (9, 5):
        try:
            result = graph.invoke({"text": SAMPLE_TICKETS[0]}, {"recursion_limit": limit})
        except GraphRecursionError as error:
            first_line = str(error).splitlines()[0]
            print(f"recursion_limit={limit}: GraphRecursionError: {first_line}")
        else:
            print(
                f"recursion_limit={limit}: reply={result['reply']!r} problems={result['problems']}"
            )
    # endregion


if __name__ == "__main__":
    main()

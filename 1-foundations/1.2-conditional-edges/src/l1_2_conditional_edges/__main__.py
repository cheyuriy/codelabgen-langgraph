"""Live run: draw the ticket graph, invoke it, and stream its node updates."""

from l1_2_conditional_edges.graph import build_graph

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
    # We pass only "text"; the nodes fill in clean_text, priority, category
    # and the reply of the one queue node that ran.
    print("== invoke() ==")
    for ticket in SAMPLE_TICKETS:
        print(graph.invoke({"text": ticket}))
    # endregion

    # region stream_updates
    # stream_mode="updates" yields one {node_name: partial_update} per step,
    # which shows exactly what each node returned and that only one queue
    # node ran.
    print("\n== stream(stream_mode='updates') ==")
    for update in graph.stream({"text": "  Refund   please "}, stream_mode="updates"):
        print(update)
    # endregion


if __name__ == "__main__":
    main()

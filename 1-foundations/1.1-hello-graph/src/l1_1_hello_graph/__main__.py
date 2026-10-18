"""Live run: draw the ticket graph, invoke it, and stream its node updates."""

from l1_1_hello_graph.graph import build_graph

SAMPLE_TICKETS = [
    "  The site is DOWN,\n  please fix ASAP!  ",
    "How do I change my   email address?",
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
    # We pass only "text"; the nodes fill in clean_text and priority.
    print("== invoke() ==")
    for ticket in SAMPLE_TICKETS:
        print(graph.invoke({"text": ticket}))
    # endregion

    # region stream_updates
    # stream_mode="updates" yields one {node_name: partial_update} per step,
    # which shows exactly what each node returned.
    print("\n== stream(stream_mode='updates') ==")
    for update in graph.stream({"text": "  Refund   please "}, stream_mode="updates"):
        print(update)
    # endregion


if __name__ == "__main__":
    main()

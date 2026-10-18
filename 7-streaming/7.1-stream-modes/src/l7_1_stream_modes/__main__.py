"""Live run for lesson 7.1: stream one order four ways.

The same pick -> pack -> ship run is streamed with stream_mode="values",
with stream_mode="updates", with a list of modes (v1 tuples) and with
version="v2" (typed StreamPart dicts).
"""

from l7_1_stream_modes.orders import OrderState, build_graph
from l7_1_stream_modes.render import describe

# The input: only order_id and items. The nodes fill in status, box and tracking.
ORDER: OrderState = {"order_id": "A-1001", "items": ["PEN", "NOTEBOOK"]}


def main() -> None:
    """Stream the same order through the graph in four ways and print each chunk."""
    graph = build_graph()

    # region values_mode
    print("== stream_mode='values': the whole state after every step ==")
    # The FIRST chunk is the input itself (written in the input step, before
    # any node runs), then the full state after each super-step: 1 + 3 chunks.
    # Good for a UI that re-renders the whole order; costly when the state is big.
    for state in graph.stream(ORDER, stream_mode="values"):
        print(f"  {state}")
    print()
    # endregion

    # region updates_mode
    print("== stream_mode='updates': only what each node returned ==")
    # Each chunk is {node_name: what_the_node_returned}; there is no chunk for
    # the input. "updates" is also the default stream_mode of a compiled
    # StateGraph, so graph.stream(ORDER) prints the same. Nodes that run in
    # parallel in one step arrive as separate chunks, in no guaranteed order.
    for chunk in graph.stream(ORDER, stream_mode="updates"):
        print(f"  {chunk}")
    print()
    # endregion

    # region multiple_modes
    print("== stream_mode=['values', 'updates'] (v1): (mode, chunk) tuples ==")
    # With a list, the v1 output changes shape: every chunk becomes a
    # (mode, chunk) tuple, so the loop has to change when you go from one mode
    # to several. The order of the list does not change the order of the
    # chunks: step by step, the updates of a step come before the values after it.
    for mode, chunk in graph.stream(ORDER, stream_mode=["values", "updates"]):
        print(f"  {mode:<7} {chunk}")
    print()
    # endregion

    # region v2_parts
    print("== version='v2': every chunk is a StreamPart dict ==")
    # version="v2" (opt-in since 1.1; v1 stays the default) gives every chunk
    # the same dict shape whether you stream one mode or several, so one loop
    # that branches on part["type"] works for both. It is the stream
    # counterpart of invoke(version="v2") returning GraphOutput (lesson 6.1).
    # The parts are collected into a list here only so the keys of the first
    # two can be printed; in real code, iterate over the stream directly.
    parts = list(graph.stream(ORDER, stream_mode=["values", "updates"], version="v2"))
    print(f"  values part keys:  {sorted(parts[0])}")
    print(f"  updates part keys: {sorted(parts[1])}")
    for part in parts:
        print(f"  {describe(part)}")
    # endregion


if __name__ == "__main__":
    main()

"""Live run for lesson 7.2: stream the order's custom progress events four ways.

The same pick -> pack -> ship run is streamed with stream_mode="custom" alone,
with ["updates", "custom"] in version="v2", and with "updates" only (where the
writer calls go nowhere); finally the nodes are called directly, outside a run.
"""

from langgraph.runtime import Runtime

from l7_2_custom_stream_data.orders import OrderState, build_graph, pack, ship
from l7_2_custom_stream_data.render import describe

# The input: only order_id and items. The nodes fill in status, box and tracking.
ORDER: OrderState = {"order_id": "A-1001", "items": ["PEN", "NOTEBOOK"]}


def main() -> None:
    """Stream the order's progress events in four ways and print each chunk."""
    graph = build_graph()

    # region custom_mode
    print("== stream_mode='custom': only what the nodes wrote ==")
    # With "custom" alone (v1) every chunk is the bare value a node passed to
    # its writer. Nothing from the state, and no node names unless you put
    # them into the payload yourself (that is why the payloads carry "node").
    for data in graph.stream(ORDER, stream_mode="custom"):
        print(f"  {data}")
    print()
    # endregion

    # region custom_with_updates
    print("== stream_mode=['updates', 'custom'], version='v2': progress between the updates ==")
    # A custom part is {"type": "custom", "ns": ..., "data": ...}. The two pack
    # progress parts arrive BEFORE pack's updates part: the writer sends while
    # the node runs, and the update is only emitted when the node returns.
    # Requesting "custom" also turns on eager streaming, so a slow node's
    # progress reaches the caller live. The order of the mode list does not
    # matter: ["custom", "updates"] gives the same sequence.
    for part in graph.stream(ORDER, stream_mode=["updates", "custom"], version="v2"):
        print(f"  {describe(part)}")
    print()
    # endregion

    # region writer_without_custom
    print("== stream_mode='updates' only: the writer calls go nowhere ==")
    # When "custom" is not among the requested modes, the run gives every node
    # a writer that does nothing, so the nodes need no `if streaming:` check.
    # The progress is simply dropped, with no error and no warning; the same
    # happens with invoke().
    for chunk in graph.stream(ORDER, stream_mode="updates"):
        print(f"  {chunk}")
    print(f"  invoke() -> status={graph.invoke(ORDER)['status']}")
    print()
    # endregion

    # region writer_outside_run
    print("== the nodes called directly, outside a run ==")
    # Outside a graph run there is no run context, so get_stream_writer()
    # inside pack raises RuntimeError.
    try:
        pack(ORDER)
    except RuntimeError as error:
        print(f"  pack(ORDER) -> RuntimeError: {error}")
    # A node that takes the writer through `runtime` is an ordinary function:
    # call it with any Runtime, here one whose writer appends to a list.
    # (A plain Runtime() also works: its default stream_writer does nothing.)
    written: list = []
    result = ship(ORDER, Runtime(stream_writer=written.append))
    print(f"  ship(ORDER, Runtime(stream_writer=written.append)) -> {result}")
    print(f"  written: {written}")
    # endregion


if __name__ == "__main__":
    main()

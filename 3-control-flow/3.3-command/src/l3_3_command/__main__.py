"""Live run: price, check, then let decide update the state and route with Command."""

import time

from langgraph.errors import InvalidUpdateError

from l3_3_command.checks import NoReducerOrderState, build_graph, decide, route_lines

# The orders no longer carry a total: the graph computes it from the lines.
ADA = {
    "order_id": "A-1001",
    "items": {"PEN": 4, "NOTEBOOK": 1},
    "balance": 50.0,
    "address": "12 Main St, Berlin, de",
}
BOB = {
    "order_id": "B-1002",
    "items": {"PEN": 2, "MUG": 1},
    "balance": 10.0,
    "address": "5 Elm Rd, Leeds, uk",
}
CLEO = {
    "order_id": "C-1003",
    "items": {"PEN": 1},
    "balance": 10.0,
    "address": "1 Rue Verte, Paris, us",
}
DORA = {
    "order_id": "D-1004",
    "items": {"PEN": 2, "NOTEBOOK": 1, "MUG": 1},
    "balance": 30.0,
    "address": "3 Canal St, Amsterdam, nl",
}


def main() -> None:
    """Run the five demo sections."""
    graph = build_graph()

    # region step_by_step
    print("== Ada A-1001: state after each super-step ==")
    # Calling the router directly shows what it hands to the graph.
    print("route_lines sends:")
    for send in route_lines(ADA):
        print(f"  {send!r}")
    # stream_mode="values" yields one chunk for the input, then the full
    # state after each super-step. Skip the input chunk.
    chunks = list(graph.stream(ADA, stream_mode="values"))
    for step, chunk in enumerate(chunks[1:], start=1):
        skus = [line["sku"] for line in chunk.get("lines", [])]
        total = chunk.get("total", "-")
        checks = [r["check"] for r in chunk.get("results", [])]
        country = chunk.get("country", "-")
        decision = chunk.get("decision", "-")
        notice = chunk.get("notice", "-")
        print(
            f"step {step}: lines={skus} total={total} results={checks} "
            f"country={country} decision={decision} notice={notice}"
        )
    print(f"decision: {chunks[-1]['decision']}")
    # Calling the node directly shows the Command it hands to the graph, as
    # route_lines' Sends are shown above.
    print("decide returned:")
    print(f"  {decide(chunks[-1])!r}")
    # endregion

    # region decisions
    print()
    print("== Decisions ==")
    for order in (BOB, CLEO, DORA):
        final = graph.invoke(order)
        print(final["order_id"])
        # The total is rebuilt from the lines the price_line tasks stored.
        parts = " + ".join(f"{ln['sku']} x{ln['qty']} {ln['amount']}" for ln in final["lines"])
        print(f"  total {final['total']} = {parts}")
        for r in final["results"]:  # stored order, not used by decide
            status = "OK" if r["ok"] else "FAIL"
            print(f"  {r['check']:<8} {status:<4}  {r['detail']}")
        print(f"  -> {final['decision']}")
        for problem in final["problems"]:
            print(f"     {problem}")
        # Written by whichever node decide's Command chose.
        print(f"  notice: {final['notice']}")
    # endregion

    # region routes_drawing
    print()
    print("== Where decide can go ==")
    # build_graph adds no edge out of decide: these three dotted edges come
    # from its return annotation.
    for line in graph.get_graph().draw_mermaid().splitlines():
        if line.strip().startswith("decide -"):
            print(f"  {line.strip()}")
    # endregion

    # region no_reducer_demo
    print()
    print("== Same nodes, no reducer on results ==")
    try:
        build_graph(NoReducerOrderState).invoke(ADA)
    except InvalidUpdateError as e:
        # Three nodes wrote "results" in one step and nothing says how to merge them.
        print(f"InvalidUpdateError: {str(e).splitlines()[0]}")
    # endregion

    # region max_concurrency_demo
    print()
    print("== Dora D-1004: 3 price lookups, max_concurrency ==")
    for limit in (None, 2, 1):
        # max_concurrency is a run config key: the most tasks run at once.
        # The sync executor uses it as its thread-pool size for the whole run.
        config = {} if limit is None else {"max_concurrency": limit}
        start = time.perf_counter()
        final = graph.invoke(DORA, config)
        elapsed = time.perf_counter() - start
        print(f"max_concurrency={limit}: total {final['total']} in {elapsed:.1f} s")
    # endregion


if __name__ == "__main__":
    main()

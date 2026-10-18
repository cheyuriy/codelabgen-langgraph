"""Live run: watch three checks run in parallel and join in decide."""

from langgraph.errors import InvalidUpdateError

from l3_1_parallel_branches.checks import NoReducerOrderState, build_graph

ADA = {
    "order_id": "A-1001",
    "items": {"PEN": 4, "NOTEBOOK": 1},
    "total": 10.0,
    "balance": 50.0,
    "address": "12 Main St, Berlin, de",
}
BOB = {
    "order_id": "B-1002",
    "items": {"PEN": 2, "MUG": 1},
    "total": 60.0,
    "balance": 20.0,
    "address": "5 Elm Rd, Leeds, uk",
}
CLEO = {
    "order_id": "C-1003",
    "items": {"PEN": 1},
    "total": 1.5,
    "balance": 10.0,
    "address": "1 Rue Verte, Paris, us",
}


def main() -> None:
    """Run the three demo sections."""
    graph = build_graph()

    # region step_by_step
    print("== Ada A-1001: state after each super-step ==")
    # stream_mode="values" yields one chunk for the input, then the full
    # state after each super-step. Skip the input chunk.
    chunks = list(graph.stream(ADA, stream_mode="values"))
    for step, chunk in enumerate(chunks[1:], start=1):
        checks = [r["check"] for r in chunk.get("results", [])]
        country = chunk.get("country", "-")
        decision = chunk.get("decision", "-")
        print(f"step {step}: results={checks} country={country} decision={decision}")
    print(f"decision: {chunks[-1]['decision']}")
    # endregion

    # region decisions
    print()
    print("== Decisions ==")
    for order in (BOB, CLEO):
        final = graph.invoke(order)
        print(final["order_id"])
        for r in final["results"]:  # stored order, not used by decide
            status = "OK" if r["ok"] else "FAIL"
            print(f"  {r['check']:<8} {status:<4}  {r['detail']}")
        print(f"  -> {final['decision']}")
        for problem in final["problems"]:
            print(f"     {problem}")
    # endregion

    # region no_reducer_demo
    print()
    print("== Same nodes, no reducer on results ==")
    try:
        build_graph(NoReducerOrderState).invoke(ADA)
    except InvalidUpdateError as e:
        # Three nodes wrote "results" in step 1 and nothing says how to merge them.
        print(f"InvalidUpdateError: {str(e).splitlines()[0]}")
    # endregion


if __name__ == "__main__":
    main()

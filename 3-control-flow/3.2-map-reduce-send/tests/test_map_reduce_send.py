"""Offline tests for lesson 3.2: map-reduce with Send before the parallel checks."""

import threading

import pytest
from l3_2_map_reduce_send import checks
from l3_2_map_reduce_send.__main__ import ADA, BOB, CLEO, DORA
from l3_2_map_reduce_send.checks import (
    NoReducerOrderState,
    OrderState,
    build_graph,
    check_address,
    check_payment,
    check_stock,
    decide,
    normalize_address,
    price_line,
    route_lines,
    sum_total,
)
from l3_2_map_reduce_send.pricing import PriceTask
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph


def test_route_lines_sends_one_task_per_line() -> None:
    """route_lines turns each item into a Send with its own payload."""
    sends = route_lines(ADA)
    assert [s.node for s in sends] == ["price_line", "price_line"]
    assert [s.arg for s in sends] == [{"sku": "PEN", "qty": 4}, {"sku": "NOTEBOOK", "qty": 1}]
    assert route_lines({**ADA, "items": {}}) == []


def test_price_line_takes_a_price_task() -> None:
    """The map task works on its own payload, without any order state."""
    assert price_line({"sku": "MUG", "qty": 2}) == {
        "lines": [{"sku": "MUG", "qty": 2, "amount": 16.0}]
    }


def test_computed_totals_and_decisions() -> None:
    """The total comes from the priced lines and feeds the payment check."""
    graph = build_graph()
    ada = graph.invoke(ADA)
    assert ada["total"] == 10.0
    assert sorted(line["sku"] for line in ada["lines"]) == ["NOTEBOOK", "PEN"]
    assert ada["decision"] == "approved"
    assert ada["problems"] == []
    assert sorted(r["check"] for r in ada["results"]) == ["address", "payment", "stock"]

    bob = graph.invoke(BOB)
    assert bob["total"] == 11.0
    assert bob["decision"] == "on_hold"
    assert bob["problems"] == [
        "address: no shipping to UK",
        "payment: balance 10.0 < total 11.0",
        "stock: MUG 1>0",
    ]

    cleo = graph.invoke(CLEO)
    assert cleo["total"] == 1.5
    assert cleo["problems"] == ["address: no shipping to US"]


def test_super_steps_on_1_2_16() -> None:
    """Pinned behaviour of langgraph 1.2.16, partly an implementation detail.

    Five super-steps: price_line x2, sum_total, the three checks,
    check_address, decide. In 1.2.16 a step's writes are applied sorted by
    task path, and a Send task's path holds its index in the returned list,
    so lines are stored in Send-list order. That is not a documented
    guarantee; stream order inside one step is not checked.
    """
    graph = build_graph()
    chunks = list(graph.stream(ADA, stream_mode="values"))
    assert len(chunks) == 6
    assert len(chunks[1]["lines"]) == 2
    assert "total" not in chunks[1]
    assert chunks[2]["total"] == 10.0
    assert [r["check"] for r in chunks[3]["results"]] == ["payment", "stock"]
    assert chunks[5]["decision"] == "approved"
    assert [line["sku"] for line in chunks[-1]["lines"]] == ["PEN", "NOTEBOOK"]

    reversed_ada = {**ADA, "items": dict(reversed(list(ADA["items"].items())))}
    final = graph.invoke(reversed_ada)
    assert [line["sku"] for line in final["lines"]] == ["NOTEBOOK", "PEN"]


def test_sum_total_is_order_independent() -> None:
    """The reduce step gives the same total whatever order the lines are in."""
    lines = [
        {"sku": "PEN", "qty": 2, "amount": 3.0},
        {"sku": "MUG", "qty": 1, "amount": 8.0},
    ]
    assert sum_total({"lines": lines}) == {"total": 11.0}
    assert sum_total({"lines": list(reversed(lines))}) == {"total": 11.0}


def test_max_concurrency_caps_map_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """max_concurrency limits how many price_line tasks run at the same time."""
    lock = threading.Lock()
    running = 0
    peak = 0

    def counting_price_line(task: PriceTask) -> dict:
        """Count concurrent calls, then delegate to the real price_line."""
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        try:
            return price_line(task)
        finally:
            with lock:
                running -= 1

    # build_graph reads checks.price_line when it adds the node.
    monkeypatch.setattr(checks, "price_line", counting_price_line)
    graph = build_graph()

    final = graph.invoke(DORA, {"max_concurrency": 1})
    assert peak == 1
    assert final["total"] == 15.0

    peak = 0
    final = graph.invoke(DORA, {"max_concurrency": 2})
    assert peak <= 2
    assert final["total"] == 15.0


def test_decide_is_order_independent() -> None:
    """decide gives the same answer whatever order the results arrive in."""
    state = {**BOB, "total": 11.0}
    state.update(normalize_address(state))
    results = (
        check_stock(state)["results"]
        + check_payment(state)["results"]
        + check_address(state)["results"]
    )
    forward = decide({**state, "results": results})
    backward = decide({**state, "results": list(reversed(results))})
    assert forward == backward
    assert forward["decision"] == "on_hold"


def _count_decide(graph) -> int:
    """Count how many times decide reports an update for Ada's order."""
    return sum(1 for update in graph.stream(ADA, stream_mode="updates") if "decide" in update)


def test_waiting_edge_joins_once() -> None:
    """The list edge runs decide once; three separate edges run it twice."""
    assert _count_decide(build_graph()) == 1

    builder = StateGraph(OrderState)
    builder.add_node("price_line", price_line)
    builder.add_node("sum_total", sum_total)
    builder.add_node("check_stock", check_stock)
    builder.add_node("check_payment", check_payment)
    builder.add_node("normalize_address", normalize_address)
    builder.add_node("check_address", check_address)
    builder.add_node("decide", decide)
    builder.add_conditional_edges(START, route_lines, ["price_line"])
    builder.add_edge("price_line", "sum_total")
    builder.add_edge("sum_total", "check_stock")
    builder.add_edge("sum_total", "check_payment")
    builder.add_edge("sum_total", "normalize_address")
    builder.add_edge("normalize_address", "check_address")
    # Separate edges: each fires as soon as its own source finishes.
    builder.add_edge("check_stock", "decide")
    builder.add_edge("check_payment", "decide")
    builder.add_edge("check_address", "decide")
    builder.add_edge("decide", END)
    assert _count_decide(builder.compile()) == 2


def test_no_reducer_raises() -> None:
    """Without a reducer on results the checks clash; lines keeps its reducer."""
    with pytest.raises(InvalidUpdateError) as exc_info:
        build_graph(NoReducerOrderState).invoke(ADA)
    assert "At key 'results'" in str(exc_info.value)

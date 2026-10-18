"""Offline tests for lesson 3.3: decide updates the state and routes with Command."""

import threading

import pytest
from l3_3_command import checks
from l3_3_command.__main__ import ADA, BOB, CLEO, DORA
from l3_3_command.checks import (
    NoReducerOrderState,
    OrderState,
    approve,
    build_graph,
    cancel,
    check_address,
    check_payment,
    check_stock,
    decide,
    hold,
    normalize_address,
    price_line,
    route_lines,
    sum_total,
)
from l3_3_command.pricing import PriceTask
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

BOB_PROBLEMS = [
    "address: no shipping to UK",
    "payment: balance 10.0 < total 11.0",
    "stock: MUG 1>0",
]


def _checked_state(order: dict, total: float) -> dict:
    """Build the state decide sees: the order, its total and all three results."""
    state = {**order, "total": total}
    state.update(normalize_address(state))
    state["results"] = (
        check_stock(state)["results"]
        + check_payment(state)["results"]
        + check_address(state)["results"]
    )
    return state


def _node_names(graph, order: dict) -> list[str]:
    """The node names in the order their updates were streamed."""
    return [name for update in graph.stream(order, stream_mode="updates") for name in update]


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


def test_decide_returns_a_command_for_each_outcome() -> None:
    """decide hands back one Command: the state update plus the next node."""
    bob = decide(_checked_state(BOB, 11.0))
    assert isinstance(bob, Command)
    assert bob.goto == "cancel"
    assert bob.update == {"decision": "cancelled", "problems": BOB_PROBLEMS}

    dora = decide(_checked_state(DORA, 15.0))
    assert isinstance(dora, Command)
    assert dora.goto == "hold"
    assert dora.update == {"decision": "on_hold", "problems": ["stock: MUG 1>0"]}

    ada = decide(_checked_state(ADA, 10.0))
    assert isinstance(ada, Command)
    assert ada.goto == "approve"
    assert ada.update == {"decision": "approved", "problems": []}


def test_route_nodes_write_only_the_notice() -> None:
    """Each route node returns just the customer notice."""
    assert approve(ADA) == {"notice": "A-1001 approved: 5 items to pack"}
    assert hold({**DORA, "problems": ["stock: MUG 1>0"]}) == {
        "notice": "D-1004 on hold: stock: MUG 1>0"
    }
    assert cancel({**BOB, "country": "UK"}) == {"notice": "B-1002 cancelled: we do not ship to UK"}


def test_end_to_end_decisions_and_notices() -> None:
    """The node decide routes to writes the matching notice."""
    graph = build_graph()
    ada = graph.invoke(ADA)
    assert ada["total"] == 10.0
    assert sorted(line["sku"] for line in ada["lines"]) == ["NOTEBOOK", "PEN"]
    assert ada["decision"] == "approved"
    assert ada["problems"] == []
    assert ada["notice"] == "A-1001 approved: 5 items to pack"

    bob = graph.invoke(BOB)
    assert bob["total"] == 11.0
    assert bob["decision"] == "cancelled"
    assert bob["problems"] == BOB_PROBLEMS
    assert bob["notice"] == "B-1002 cancelled: we do not ship to UK"

    cleo = graph.invoke(CLEO)
    assert cleo["total"] == 1.5
    assert cleo["decision"] == "cancelled"
    assert cleo["problems"] == ["address: no shipping to US"]
    assert cleo["notice"] == "C-1003 cancelled: we do not ship to US"

    dora = graph.invoke(DORA)
    assert dora["decision"] == "on_hold"
    assert dora["problems"] == ["stock: MUG 1>0"]
    assert dora["notice"] == "D-1004 on hold: stock: MUG 1>0"


def test_only_the_chosen_node_runs() -> None:
    """goto runs one route node; the update chunk shows Command.update only."""
    graph = build_graph()
    bob_names = _node_names(graph, BOB)
    assert bob_names[-2:] == ["decide", "cancel"]
    assert "approve" not in bob_names
    assert "hold" not in bob_names

    dora_names = _node_names(graph, DORA)
    assert dora_names[-2:] == ["decide", "hold"]
    assert "approve" not in dora_names
    assert "cancel" not in dora_names

    decide_updates = [
        update["decide"]
        for update in graph.stream(BOB, stream_mode="updates")
        if "decide" in update
    ]
    assert decide_updates == [{"decision": "cancelled", "problems": BOB_PROBLEMS}]


def test_annotation_declares_the_routes() -> None:
    """No edge leaves decide; its return annotation supplies the destinations."""
    graph = build_graph()
    assert not any(source == "decide" for source, _ in graph.builder.edges)
    assert "decide" not in graph.builder.branches
    assert graph.builder.nodes["decide"].ends == ("approve", "hold", "cancel")

    edges = [e for e in graph.get_graph().edges if e.source == "decide"]
    assert len(edges) == 3
    assert {e.target for e in edges} == {"approve", "cancel", "hold"}
    assert all(e.conditional for e in edges)


def test_without_annotation_only_the_drawing_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the return hint the run is the same but the drawing loses the routes."""
    original = checks.decide

    def decide_unannotated(state: OrderState):  # no return hint, on purpose
        """The real decide, without a return annotation."""
        return original(state)

    # build_graph reads checks.decide when it adds the node.
    monkeypatch.setattr(checks, "decide", decide_unannotated)
    graph = build_graph()

    bob = graph.invoke(BOB)
    assert bob["decision"] == "cancelled"
    assert bob["notice"] == "B-1002 cancelled: we do not ship to UK"

    edges = [e for e in graph.get_graph().edges if e.source == "decide"]
    assert [(e.source, e.target) for e in edges] == [("decide", "__end__")]
    assert not edges[0].conditional


def test_super_steps_on_1_2_16() -> None:
    """Pinned behaviour of langgraph 1.2.16, partly an implementation detail.

    Six super-steps: price_line x2, sum_total, the three checks,
    check_address, decide, then the route node decide chose. In 1.2.16 a
    step's writes are applied sorted by task path, and a Send task's path
    holds its index in the returned list, so lines are stored in Send-list
    order. That is not a documented guarantee; stream order inside one step
    is not checked.
    """
    graph = build_graph()
    chunks = list(graph.stream(ADA, stream_mode="values"))
    assert len(chunks) == 7
    assert len(chunks[1]["lines"]) == 2
    assert "total" not in chunks[1]
    assert chunks[2]["total"] == 10.0
    assert [r["check"] for r in chunks[3]["results"]] == ["payment", "stock"]
    assert chunks[5]["decision"] == "approved"
    assert "notice" not in chunks[5]
    assert chunks[6]["notice"] == "A-1001 approved: 5 items to pack"
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
    """decide gives the same Command whatever order the results arrive in."""
    state = _checked_state(BOB, 11.0)
    forward = decide(state)
    backward = decide({**state, "results": list(reversed(state["results"]))})
    # Command is a dataclass, so == compares update and goto.
    assert forward == backward
    assert forward.goto == "cancel"


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
    builder.add_node("approve", approve)
    builder.add_node("hold", hold)
    builder.add_node("cancel", cancel)
    builder.add_conditional_edges(START, route_lines, ["price_line"])
    builder.add_edge("price_line", "sum_total")
    builder.add_edge("sum_total", "check_stock")
    builder.add_edge("sum_total", "check_payment")
    builder.add_edge("sum_total", "normalize_address")
    builder.add_edge("normalize_address", "check_address")
    # Separate edges: each fires as soon as its own source finishes, so
    # decide first runs before check_address has reported.
    builder.add_edge("check_stock", "decide")
    builder.add_edge("check_payment", "decide")
    builder.add_edge("check_address", "decide")
    builder.add_edge("approve", END)
    builder.add_edge("hold", END)
    builder.add_edge("cancel", END)
    assert _count_decide(builder.compile()) == 2


def test_no_reducer_raises() -> None:
    """Without a reducer on results the checks clash; lines keeps its reducer."""
    with pytest.raises(InvalidUpdateError) as exc_info:
        build_graph(NoReducerOrderState).invoke(ADA)
    assert "At key 'results'" in str(exc_info.value)

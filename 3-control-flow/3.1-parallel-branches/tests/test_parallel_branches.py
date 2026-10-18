"""Offline tests for lesson 3.1: parallel branches and a waiting-edge join."""

import pytest
from l3_1_parallel_branches.__main__ import ADA, BOB, CLEO
from l3_1_parallel_branches.checks import (
    NoReducerOrderState,
    OrderState,
    build_graph,
    check_address,
    check_payment,
    check_stock,
    decide,
    normalize_address,
)
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph


def test_ada_is_approved() -> None:
    """All three checks pass for Ada, so the order is approved."""
    final = build_graph().invoke(ADA)
    assert final["decision"] == "approved"
    assert final["problems"] == []
    assert len(final["results"]) == 3
    assert sorted(r["check"] for r in final["results"]) == ["address", "payment", "stock"]
    assert final["country"] == "DE"


def test_bob_and_cleo_are_on_hold() -> None:
    """Problems are listed in check-name order."""
    graph = build_graph()
    bob = graph.invoke(BOB)
    assert bob["decision"] == "on_hold"
    assert bob["problems"] == [
        "address: no shipping to UK",
        "payment: balance 20.0 < total 60.0",
        "stock: MUG 1>0",
    ]
    cleo = graph.invoke(CLEO)
    assert cleo["decision"] == "on_hold"
    assert cleo["problems"] == ["address: no shipping to US"]


def test_write_order_on_1_2_16() -> None:
    """Pinned behaviour of langgraph 1.2.16, an implementation detail.

    In 1.2.16 the writes of one super-step are applied sorted by task path
    (the node name here), and earlier steps come first. This is not a
    documented guarantee; it pins what this version does. Stream order
    inside one step is not checked.
    """
    graph = build_graph()
    final = graph.invoke(ADA)
    assert [r["check"] for r in final["results"]] == ["payment", "stock", "address"]

    chunks = list(graph.stream(ADA, stream_mode="values"))
    after_step_1, after_step_2 = chunks[1], chunks[2]
    assert [r["check"] for r in after_step_1["results"]] == ["payment", "stock"]
    assert after_step_1["country"] == "DE"
    assert [r["check"] for r in after_step_2["results"]] == ["payment", "stock", "address"]


def test_decide_is_order_independent() -> None:
    """decide gives the same answer whatever order the results arrive in."""
    state = dict(BOB)
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
    builder.add_node("check_stock", check_stock)
    builder.add_node("check_payment", check_payment)
    builder.add_node("normalize_address", normalize_address)
    builder.add_node("check_address", check_address)
    builder.add_node("decide", decide)
    builder.add_edge(START, "check_stock")
    builder.add_edge(START, "check_payment")
    builder.add_edge(START, "normalize_address")
    builder.add_edge("normalize_address", "check_address")
    # Separate edges: each fires as soon as its own source finishes.
    builder.add_edge("check_stock", "decide")
    builder.add_edge("check_payment", "decide")
    builder.add_edge("check_address", "decide")
    builder.add_edge("decide", END)
    assert _count_decide(builder.compile()) == 2


def test_no_reducer_raises() -> None:
    """Without a reducer, three writes to results in one step are an error."""
    with pytest.raises(InvalidUpdateError) as exc_info:
        build_graph(NoReducerOrderState).invoke(ADA)
    assert "At key 'results'" in str(exc_info.value)

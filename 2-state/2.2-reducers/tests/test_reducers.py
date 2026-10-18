"""Offline tests: reducers in the order pipeline."""

import copy
import operator
from typing import Annotated, TypedDict

import pytest
from l2_2_reducers.typed_dict_order import KIT_ITEM, LineItem, build_graph, merge_items
from langgraph.errors import InvalidUpdateError
from langgraph.graph import START, StateGraph

PEN4: LineItem = {"sku": "PEN", "quantity": 4, "unit_price": 1.5}
NOTEBOOK3: LineItem = {"sku": "NOTEBOOK", "quantity": 3, "unit_price": 4.0}
NOTEBOOK2: LineItem = {"sku": "NOTEBOOK", "quantity": 2, "unit_price": 4.0}
MUG1: LineItem = {"sku": "MUG", "quantity": 1, "unit_price": 8.0}
BOB_CART: list[LineItem] = [
    {"sku": "PEN", "quantity": 3, "unit_price": 1.5},
    {"sku": "NOTEBOOK", "quantity": 1, "unit_price": 4.0},
]
EXTRAS = {"tax_rate": 0.2, "currency": "EUR"}


def test_ada_stock_check_through_merge_items() -> None:
    """check_stock's capped lines update NOTEBOOK and remove MUG."""
    order = {"customer": "Ada", "items": [PEN4, NOTEBOOK3, MUG1], **EXTRAS}
    result = build_graph().invoke(order)
    assert result["items"] == [PEN4, NOTEBOOK2]
    assert result["subtotal"] == 14.0
    assert result["total"] == 16.8
    assert result["log"] == [
        "check_stock: NOTEBOOK 3->2, MUG 1->0",
        "apply_bundle: no bundle",
        "compute_subtotal: 14.0",
        "apply_tax: 16.8 EUR",
    ]


def test_bob_bundle_overwrites_cart() -> None:
    """Overwrite replaces the cart; the input log line stays first."""
    order = {"customer": "Bob", "items": BOB_CART, "log": ["web: checkout"], **EXTRAS}
    result = build_graph().invoke(order)
    assert result["items"] == [KIT_ITEM]
    assert result["total"] == 7.2
    assert len(result["log"]) == 5
    assert result["log"][0] == "web: checkout"


def test_merge_items_upsert() -> None:
    """Replace keeps position, new sku appends, quantity 0 removes."""
    current = [PEN4, NOTEBOOK3, MUG1]
    before = copy.deepcopy(current)
    cup: LineItem = {"sku": "CUP", "quantity": 1, "unit_price": 2.0}
    mug0: LineItem = {**MUG1, "quantity": 0}
    merged = merge_items(current, [NOTEBOOK2, cup, mug0])
    assert merged == [PEN4, NOTEBOOK2, cup]
    assert current == before  # the stored value is not mutated
    # Without Overwrite the kit would be appended next to PEN and NOTEBOOK.
    assert len(merge_items(BOB_CART, [KIT_ITEM])) == 3


def test_invoke_input_goes_through_reducer() -> None:
    """Two PEN lines in the input collapse into one; the later one wins."""
    pen1: LineItem = {"sku": "PEN", "quantity": 1, "unit_price": 1.5}
    pen2: LineItem = {"sku": "PEN", "quantity": 2, "unit_price": 1.5}
    result = build_graph().invoke({"customer": "Cy", "items": [pen1, pen2], **EXTRAS})
    assert result["items"] == [pen2]


class PlainLog(TypedDict):
    """A log without a reducer: one write per step only."""

    log: list[str]


class AddedLog(TypedDict):
    """The same log with operator.add."""

    log: Annotated[list[str], operator.add]


def _fan_out(schema: type) -> StateGraph:
    """Two nodes both wired from START, each writing one log line."""
    builder = StateGraph(schema)
    builder.add_node("a", lambda state: {"log": ["a"]})
    builder.add_node("b", lambda state: {"log": ["b"]})
    builder.add_edge(START, "a")
    builder.add_edge(START, "b")
    return builder


def test_parallel_writes_need_a_reducer() -> None:
    """Without a reducer two writes in one step fail; operator.add keeps both."""
    with pytest.raises(InvalidUpdateError):
        _fan_out(PlainLog).compile().invoke({"log": []})
    result = _fan_out(AddedLog).compile().invoke({"log": []})
    assert sorted(result["log"]) == ["a", "b"]

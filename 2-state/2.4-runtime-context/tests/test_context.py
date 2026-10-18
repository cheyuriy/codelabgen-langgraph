"""Offline tests: shop settings travel in the run context, not in the state."""

import pytest
from l2_4_runtime_context.typed_dict_order import (
    KIT_ITEM,
    LineItem,
    ShopContext,
    build_graph,
)

PEN4: LineItem = {"sku": "PEN", "quantity": 4, "unit_price": 1.5}
NOTEBOOK3: LineItem = {"sku": "NOTEBOOK", "quantity": 3, "unit_price": 4.0}
MUG1: LineItem = {"sku": "MUG", "quantity": 1, "unit_price": 8.0}
BOB_CART: list[LineItem] = [
    {"sku": "PEN", "quantity": 3, "unit_price": 1.5},
    {"sku": "NOTEBOOK", "quantity": 1, "unit_price": 4.0},
]
ADA_ORDER = {"customer": "Ada", "items": [PEN4, NOTEBOOK3, MUG1]}


def test_one_graph_two_contexts() -> None:
    """The same compiled graph prices with whichever context the call passes."""
    graph = build_graph()
    eu = graph.invoke(ADA_ORDER, context=ShopContext(tax_rate=0.2, currency="EUR"))
    assert eu["total"] == 16.8
    assert eu["log"][-1] == "apply_tax: 16.8 EUR"
    us = graph.invoke(ADA_ORDER, context=ShopContext(tax_rate=0.08, currency="USD"))
    assert us["total"] == 15.12
    assert us["log"][-1] == "apply_tax: 15.12 USD"
    assert set(eu) == {"customer", "items", "total", "log"}


def test_dict_context_is_coerced_and_input_settings_ignored() -> None:
    """A dict becomes a ShopContext; tax_rate/currency in the input are dropped."""
    order = {"customer": "Bob", "items": BOB_CART, "tax_rate": 0.5, "currency": "USD"}
    result = build_graph().invoke(order, context={"tax_rate": 0.0, "currency": "GBP"})
    assert result["items"] == [KIT_ITEM]
    assert result["total"] == 6.0
    assert result["log"][-1] == "apply_tax: 6.0 GBP"


def test_context_is_not_state() -> None:
    """The context schema is separate: its keys are no channels and no I/O keys."""
    graph = build_graph()
    context_schema = graph.get_context_jsonschema()
    assert set(context_schema["properties"]) == {"tax_rate", "currency"}
    assert {"tax_rate", "currency"} <= set(context_schema["required"])
    assert graph.context_schema is ShopContext
    input_keys = set(graph.get_input_jsonschema()["properties"])
    output_keys = set(graph.get_output_jsonschema()["properties"])
    for key in ("tax_rate", "currency"):
        assert key not in graph.builder.channels
        assert key not in input_keys
        assert key not in output_keys


def test_no_context_no_default() -> None:
    """Without context=, runtime.context is None and apply_tax fails."""
    with pytest.raises(AttributeError, match="tax_rate"):
        build_graph().invoke(ADA_ORDER)

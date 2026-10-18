"""Offline tests: the order pipeline under three state schemas."""

import pytest
from l2_1_state_schemas import dataclass_order, pydantic_order, typed_dict_order
from l2_1_state_schemas.dataclass_order import OrderData
from l2_1_state_schemas.pydantic_order import OrderModel
from langgraph.graph import END, START, StateGraph
from langgraph.types import GraphOutput
from pydantic import ValidationError

ORDER = {"customer": "Ada", "quantity": 3, "unit_price": 9.5}
TYPED_DICT_EXTRAS = {"tax_rate": 0.2, "currency": "EUR"}


def test_three_schemas_same_total() -> None:
    """All three graphs compute the same total for the same order."""
    td = typed_dict_order.build_graph().invoke({**ORDER, **TYPED_DICT_EXTRAS})
    dc = dataclass_order.build_graph().invoke(ORDER)
    pd = pydantic_order.build_graph().invoke(ORDER)
    assert td["total"] == 34.2
    assert dc["total"] == 34.2
    assert pd["total"] == 34.2


def test_pydantic_rejects_zero_quantity_dataclass_does_not() -> None:
    """Field(gt=0) fails on input; the dataclass lets quantity=0 through."""
    bad = {**ORDER, "quantity": 0}
    with pytest.raises(ValidationError) as exc_info:
        pydantic_order.build_graph().invoke(bad)
    assert exc_info.value.errors()[0]["loc"] == ("quantity",)
    assert dataclass_order.build_graph().invoke(bad)["total"] == 0.0


def test_pydantic_coercion_v1_vs_v2() -> None:
    """v1 keeps the stored string; v2 coerces the output into OrderModel."""
    graph = pydantic_order.build_graph()
    order = {**ORDER, "quantity": "3"}
    assert graph.invoke(order)["quantity"] == "3"

    out = graph.invoke(order, version="v2")
    assert isinstance(out, GraphOutput)
    assert isinstance(out.value, OrderModel)
    assert out.value.quantity == 3
    assert out.value.tax_rate == 0.2
    assert out.value.currency == "EUR"
    assert out.interrupts == ()


def test_v2_output_types() -> None:
    """v2 gives a dataclass for OrderData and a plain dict for a TypedDict."""
    out = dataclass_order.build_graph().invoke(ORDER, version="v2")
    assert isinstance(out.value, OrderData)
    assert out.value.total == 34.2

    td_out = typed_dict_order.build_graph().invoke({**ORDER, **TYPED_DICT_EXTRAS}, version="v2")
    assert type(td_out.value) is dict


def test_node_updates_not_validated_on_write() -> None:
    """An invalid update leaks into v1 output; v2 coercion rejects it."""

    def break_quantity(state: OrderModel) -> dict[str, int]:
        """Write a quantity that violates Field(gt=0)."""
        return {"quantity": -1}

    builder = StateGraph(OrderModel)
    builder.add_node("break_quantity", break_quantity)
    builder.add_edge(START, "break_quantity")
    builder.add_edge("break_quantity", END)
    graph = builder.compile()

    assert graph.invoke(ORDER)["quantity"] == -1
    with pytest.raises(ValidationError):
        graph.invoke(ORDER, version="v2")


def test_typed_dict_missing_key_raises_key_error() -> None:
    """Without tax_rate the TypedDict graph fails inside apply_tax."""
    with pytest.raises(KeyError):
        typed_dict_order.build_graph().invoke({**ORDER, "currency": "EUR"})

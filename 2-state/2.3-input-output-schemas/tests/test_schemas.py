"""Offline tests: input, output and private schemas in the order pipeline."""

from l2_3_input_output_schemas.typed_dict_order import (
    KIT_ITEM,
    LineItem,
    OrderDict,
    PricingState,
    build_graph,
)

PEN4: LineItem = {"sku": "PEN", "quantity": 4, "unit_price": 1.5}
NOTEBOOK3: LineItem = {"sku": "NOTEBOOK", "quantity": 3, "unit_price": 4.0}
NOTEBOOK2: LineItem = {"sku": "NOTEBOOK", "quantity": 2, "unit_price": 4.0}
MUG1: LineItem = {"sku": "MUG", "quantity": 1, "unit_price": 8.0}
BOB_CART: list[LineItem] = [
    {"sku": "PEN", "quantity": 3, "unit_price": 1.5},
    {"sku": "NOTEBOOK", "quantity": 1, "unit_price": 4.0},
]
EXTRAS = {"tax_rate": 0.2, "currency": "EUR"}
ADA_ORDER = {"customer": "Ada", "items": [PEN4, NOTEBOOK3, MUG1], **EXTRAS}


def test_ada_receipt_has_only_output_keys() -> None:
    """invoke returns the OrderOutput keys: no subtotal, no tax_rate."""
    result = build_graph().invoke(ADA_ORDER)
    assert set(result) == {"customer", "items", "total", "currency", "log"}
    assert result["items"] == [PEN4, NOTEBOOK2]
    assert result["total"] == 16.8
    assert result["log"] == [
        "check_stock: NOTEBOOK 3->2, MUG 1->0",
        "apply_bundle: no bundle",
        "compute_subtotal: 14.0",
        "apply_tax: 16.8 EUR",
    ]


def test_bob_extra_input_keys_are_dropped() -> None:
    """log and subtotal are not in OrderInput, so START drops them silently."""
    order = {
        "customer": "Bob",
        "items": BOB_CART,
        "log": ["web: checkout"],
        "subtotal": 0.0,
        **EXTRAS,
    }
    result = build_graph().invoke(order)
    assert result["items"] == [KIT_ITEM]
    assert result["total"] == 7.2
    assert len(result["log"]) == 4
    assert result["log"][0] == "check_stock: all in stock"


def test_interface_and_channels() -> None:
    """subtotal is a channel but in neither the input nor the output schema."""
    graph = build_graph()
    input_keys = set(graph.get_input_jsonschema()["properties"])
    output_keys = set(graph.get_output_jsonschema()["properties"])
    assert input_keys == {"customer", "items", "tax_rate", "currency"}
    assert output_keys == {"customer", "items", "total", "currency", "log"}
    assert "subtotal" in graph.builder.channels
    assert "subtotal" not in input_keys | output_keys
    # Each node's input schema is inferred from its first parameter's hint.
    assert graph.builder.nodes["apply_tax"].input_schema is PricingState
    assert graph.builder.nodes["compute_subtotal"].input_schema is OrderDict


def test_subtotal_travels_inside_the_graph() -> None:
    """The private subtotal shows up in the node updates, not in the receipt."""
    graph = build_graph()
    updates = list(graph.stream(ADA_ORDER, stream_mode="updates"))
    by_node = {node: update for chunk in updates for node, update in chunk.items()}
    assert by_node["compute_subtotal"] == {
        "subtotal": 14.0,
        "log": ["compute_subtotal: 14.0"],
    }
    assert "subtotal" not in graph.invoke(ADA_ORDER)


def test_input_still_goes_through_reducer() -> None:
    """OrderInput.items is plain, yet the input is merged by merge_items."""
    pen1: LineItem = {"sku": "PEN", "quantity": 1, "unit_price": 1.5}
    pen2: LineItem = {"sku": "PEN", "quantity": 2, "unit_price": 1.5}
    result = build_graph().invoke({"customer": "Cy", "items": [pen1, pen2], **EXTRAS})
    assert result["items"] == [pen2]

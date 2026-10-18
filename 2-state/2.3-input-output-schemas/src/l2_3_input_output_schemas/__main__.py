"""Live run: a narrow public interface around a private subtotal."""

from l2_3_input_output_schemas.typed_dict_order import LineItem, build_graph

ADA_CART: list[LineItem] = [
    {"sku": "PEN", "quantity": 4, "unit_price": 1.5},
    {"sku": "NOTEBOOK", "quantity": 3, "unit_price": 4.0},
    {"sku": "MUG", "quantity": 1, "unit_price": 8.0},
]
BOB_CART: list[LineItem] = [
    {"sku": "PEN", "quantity": 3, "unit_price": 1.5},
    {"sku": "NOTEBOOK", "quantity": 1, "unit_price": 4.0},
]


def fmt_items(items: list[LineItem]) -> str:
    """Render a cart as "PEN x4, NOTEBOOK x3"."""
    return ", ".join(f"{item['sku']} x{item['quantity']}" for item in items)


def main() -> None:
    """Show the interface, two orders, and the private subtotal at work."""
    graph = build_graph()

    # region interface_demo
    print("== The public interface ==")
    # The JSON schemas come from OrderInput and OrderOutput.
    print("input:  " + ", ".join(graph.get_input_jsonschema()["properties"]))
    print("output: " + ", ".join(graph.get_output_jsonschema()["properties"]))
    # The builder's channels: every key of every registered schema. subtotal
    # comes last, registered when apply_tax (hint: PricingState) was added.
    print("channels: " + ", ".join(graph.builder.channels))
    # endregion

    # region receipt_demo
    print("\n== Ada: send a cart, get a receipt ==")
    ada_order = {"customer": "Ada", "items": ADA_CART, "tax_rate": 0.2, "currency": "EUR"}
    receipt = graph.invoke(ada_order)
    # invoke returns a plain dict with only the OrderOutput keys.
    print("receipt keys: " + ", ".join(receipt))
    print(f"cart in:  {fmt_items(ADA_CART)}")
    print(f"cart out: {fmt_items(receipt['items'])}")
    print("log:")
    for line in receipt["log"]:
        print(f"  {line}")
    print(f"total: {receipt['total']} {receipt['currency']}")
    # endregion

    # region input_filter_demo
    print("\n== Bob: keys outside OrderInput are dropped ==")
    bob_order = {
        "customer": "Bob",
        "items": BOB_CART,
        "tax_rate": 0.2,
        "currency": "EUR",
        "log": ["web: checkout"],  # not in OrderInput
        "subtotal": 0.0,  # private, not in OrderInput
    }
    print("sent keys: " + ", ".join(bob_order))
    # START writes only OrderInput's keys; the rest is filtered silently,
    # without an error.
    receipt = graph.invoke(bob_order)
    print(f"cart out: {fmt_items(receipt['items'])}")
    print("log:")
    for line in receipt["log"]:
        print(f"  {line}")
    print(f"total: {receipt['total']} {receipt['currency']}")
    # endregion

    # region private_updates_demo
    print("\n== Inside the graph: subtotal travels between nodes ==")
    # stream_mode="updates" yields {node_name: update} after each node, so
    # we see the private subtotal write that the receipt hides.
    for chunk in graph.stream(ada_order, stream_mode="updates"):
        for node, update in chunk.items():
            print(f"  {node} writes: {', '.join(update)}")
    print(f"subtotal in receipt: {'subtotal' in graph.invoke(ada_order)}")
    # endregion


if __name__ == "__main__":
    main()

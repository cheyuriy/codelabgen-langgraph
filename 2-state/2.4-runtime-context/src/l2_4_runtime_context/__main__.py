"""Live run: one compiled graph, two shops, settings passed as run context."""

from l2_4_runtime_context.typed_dict_order import LineItem, ShopContext, build_graph

ADA_CART: list[LineItem] = [
    {"sku": "PEN", "quantity": 4, "unit_price": 1.5},
    {"sku": "NOTEBOOK", "quantity": 3, "unit_price": 4.0},
    {"sku": "MUG", "quantity": 1, "unit_price": 8.0},
]
BOB_CART: list[LineItem] = [
    {"sku": "PEN", "quantity": 3, "unit_price": 1.5},
    {"sku": "NOTEBOOK", "quantity": 1, "unit_price": 4.0},
]
EU_SHOP = ShopContext(tax_rate=0.2, currency="EUR")  # 20% VAT
US_SHOP = ShopContext(tax_rate=0.08, currency="USD")  # 8% sales tax


def fmt_items(items: list[LineItem]) -> str:
    """Render a cart as "PEN x4, NOTEBOOK x3"."""
    return ", ".join(f"{item['sku']} x{item['quantity']}" for item in items)


def main() -> None:
    """Show the interface, one graph serving two shops, and the context at work."""
    # Built once: the shop settings are not baked into the graph.
    graph = build_graph()
    # The caller sends only the cart; no tax_rate or currency in the input.
    ada_order = {"customer": "Ada", "items": ADA_CART}

    # region interface_demo
    print("== The public interface ==")
    # The JSON schemas come from OrderInput, OrderOutput and ShopContext.
    print("input:   " + ", ".join(graph.get_input_jsonschema()["properties"]))
    print("output:  " + ", ".join(graph.get_output_jsonschema()["properties"]))
    print("context: " + ", ".join(graph.get_context_jsonschema()["properties"]))
    # The builder's channels: tax_rate and currency are no longer among them,
    # because context is not state.
    print("channels: " + ", ".join(graph.builder.channels))
    # endregion

    # region two_shops_demo
    print("\n== One graph, two shops ==")
    receipt = graph.invoke(ada_order, context=EU_SHOP)
    # invoke still returns only the OrderOutput keys; the context is not in it.
    print("receipt keys: " + ", ".join(receipt))
    for label, shop in [("EU shop", EU_SHOP), ("US shop", US_SHOP)]:
        # context= is per call: the same compiled graph prices with each shop.
        receipt = graph.invoke(ada_order, context=shop)
        print(f"{label}: cart out {fmt_items(receipt['items'])}")
        print(f"  {receipt['log'][-1]}")
        # The receipt has no currency: the caller knows the one it passed.
        print(f"  total: {receipt['total']} {shop.currency}")
    # endregion

    # region input_filter_demo
    print("\n== Bob: shop settings in the input are ignored ==")
    # How a 2.3 caller would still send it: settings mixed into the input.
    bob_order = {"customer": "Bob", "items": BOB_CART, "tax_rate": 0.5, "currency": "USD"}
    # A plain dict works as context too.
    bob_context = {"tax_rate": 0.2, "currency": "EUR"}
    print("sent keys: " + ", ".join(bob_order))
    print(f"context: {bob_context}")
    # START drops tax_rate and currency silently (they are not in OrderInput),
    # and LangGraph turns the dict into ShopContext(**dict) before the run
    # (_coerce_context in pregel/main.py, for dataclass and pydantic schemas).
    receipt = graph.invoke(bob_order, context=bob_context)
    for line in receipt["log"]:
        print(f"  {line}")
    print(f"total: {receipt['total']} {bob_context['currency']}")
    # endregion

    # region private_updates_demo
    print("\n== Inside the graph: subtotal travels between nodes ==")
    # stream_mode="updates" yields {node_name: update} after each node. The
    # context goes to stream exactly as it goes to invoke.
    for chunk in graph.stream(ada_order, context=EU_SHOP, stream_mode="updates"):
        for node, update in chunk.items():
            print(f"  {node} writes: {', '.join(update)}")
    receipt = graph.invoke(ada_order, context=EU_SHOP)
    print(f"subtotal in receipt: {'subtotal' in receipt}")
    # endregion


if __name__ == "__main__":
    main()

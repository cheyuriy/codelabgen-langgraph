"""Live run: how reducers combine node updates with the stored state."""

from l2_2_reducers.typed_dict_order import (
    KIT_ITEM,
    LineItem,
    build_graph,
    merge_items,
)

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
    """Run two orders through the graph, then call merge_items directly."""
    graph = build_graph()

    # region stock_demo
    print("== Ada: check_stock updates lines through merge_items ==")
    order = {"customer": "Ada", "items": ADA_CART, "tax_rate": 0.2, "currency": "EUR"}
    result = graph.invoke(order)
    print(f"cart in:  {fmt_items(ADA_CART)}")
    print(f"cart out: {fmt_items(result['items'])}")
    print("log:")
    for line in result["log"]:  # one line per node, joined by operator.add
        print(f"  {line}")
    print(f"total: {result['total']} {result['currency']}")
    # endregion

    # region bundle_demo
    print("\n== Bob: apply_bundle replaces the cart with Overwrite ==")
    order = {
        "customer": "Bob",
        "items": BOB_CART,
        "tax_rate": 0.2,
        "currency": "EUR",
        # The input is written through operator.add too, so it stays first.
        "log": ["web: checkout"],
    }
    result = graph.invoke(order)
    print(f"cart in:  {fmt_items(BOB_CART)}")
    print(f"cart out: {fmt_items(result['items'])}")
    print("log:")
    for line in result["log"]:
        print(f"  {line}")
    print(f"total: {result['total']} {result['currency']}")
    # endregion

    # region reducer_calls
    print("\n== Reducers are plain functions ==")
    update: list[LineItem] = [
        {"sku": "NOTEBOOK", "quantity": 2, "unit_price": 4.0},
        {"sku": "MUG", "quantity": 0, "unit_price": 8.0},
    ]
    print(f"current: {fmt_items(ADA_CART)}")
    print(f"update:  {fmt_items(update)}")
    print(f"merged:  {fmt_items(merge_items(ADA_CART, update))}")
    # What apply_bundle would get from a plain list instead of Overwrite.
    merged = merge_items(BOB_CART, [KIT_ITEM])
    print(f"Bob's cart + [STARTER-KIT x1] without Overwrite ({len(merged)} lines):")
    for item in merged:
        print(f"  {item['sku']} x{item['quantity']} @ {item['unit_price']}")
    # endregion


if __name__ == "__main__":
    main()

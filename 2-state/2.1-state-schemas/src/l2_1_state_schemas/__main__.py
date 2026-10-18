"""Live run: the same order through three state schemas."""

from pydantic import ValidationError

from l2_1_state_schemas import dataclass_order, pydantic_order, typed_dict_order

# The order every section starts from.
ORDER = {"customer": "Ada", "quantity": 3, "unit_price": 9.5}
# The TypedDict schema has no defaults, so its caller must add these.
TYPED_DICT_EXTRAS = {"tax_rate": 0.2, "currency": "EUR"}


def main() -> None:
    """Build the three graphs and compare how they treat the same input."""
    typed_dict_graph = typed_dict_order.build_graph()
    dataclass_graph = dataclass_order.build_graph()
    pydantic_graph = pydantic_order.build_graph()

    print("== Same order, three schemas ==")
    # The default invoke (version="v1") returns a plain dict of stored values.
    result = typed_dict_graph.invoke({**ORDER, **TYPED_DICT_EXTRAS})
    print(f"TypedDict  total: {result['total']}")
    result = dataclass_graph.invoke(ORDER)
    print(f"dataclass  total: {result['total']}")
    result = pydantic_graph.invoke(ORDER)
    print(f"Pydantic   total: {result['total']}")

    # region bad_input_demo
    print("\n== Bad input: quantity=-2 ==")
    bad_order = {**ORDER, "quantity": -2}
    # TypedDict and dataclass states are never validated: -2 goes through.
    result = typed_dict_graph.invoke({**bad_order, **TYPED_DICT_EXTRAS})
    print(f"TypedDict  total: {result['total']}")
    result = dataclass_graph.invoke(bad_order)
    print(f"dataclass  total: {result['total']}")
    try:
        # LangGraph builds OrderModel(**state) for the first node's input,
        # so Field(gt=0) fails before compute_subtotal ever runs.
        pydantic_graph.invoke(bad_order)
    except ValidationError as exc:
        error = exc.errors()[0]
        loc = ".".join(str(part) for part in error["loc"])
        print(f"Pydantic   ValidationError: {loc}: {error['msg']}")
    # endregion

    # region coercion_demo
    print("\n== Pydantic coerces what nodes see, not what is stored ==")
    # The nodes get quantity=3 (int), but the channel keeps the raw "3".
    result = pydantic_graph.invoke({**ORDER, "quantity": "3"})
    print(f"quantity stored: {result['quantity']!r}")
    # tax_rate and currency are missing: defaults live in the model only,
    # and no node ever wrote them to the state.
    print(f"keys: {sorted(result)}")
    # endregion

    # region v2_output
    print("\n== Typed output with version='v2' ==")
    # The dataclass gets the int order (it would not coerce "3"); the
    # Pydantic graph gets the same string input as in the section above.
    runs = [
        (dataclass_graph, ORDER),
        (pydantic_graph, {**ORDER, "quantity": "3"}),
    ]
    for graph, order in runs:
        # version="v2" returns a GraphOutput and coerces its value into the
        # state class. Read .value and .interrupts, never out["key"].
        out = graph.invoke(order, version="v2")
        print(f"{type(out).__name__} -> {type(out.value).__name__}")
        print(f"  value: {out.value}")
        print(f"  interrupts: {out.interrupts}")
    # endregion


if __name__ == "__main__":
    main()

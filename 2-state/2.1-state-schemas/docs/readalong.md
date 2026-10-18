# 2.1 State Schemas: TypedDict, Dataclass and Pydantic — code walkthrough

The program builds the same two-node order pipeline (`compute_subtotal`, then `apply_tax`) three times, once with each kind of state schema. It then feeds the three graphs a normal order, a bad order, a string quantity, and finally asks for typed output with `version="v2"`. Run it with `./run.sh 2.1` from the course root.
The concept itself is explained in the [notes](notes.md).

The three graph modules are nearly identical on purpose. Read the first one carefully, then read the other two for the differences: the schema class and how the nodes read the state.

## [typed_dict_order.py](../src/l2_1_state_schemas/typed_dict_order.py)

The baseline: the pipeline with a `TypedDict` schema, wired the same way as in lesson 1.1.

- [`OrderDict`](../src/l2_1_state_schemas/typed_dict_order.py#L17-L30) lists seven keys. `StateGraph` only uses the class to learn the key names and their types. It turns each key into a channel. At run time a `TypedDict` is a plain `dict`, and Python does not check it. That gives no defaults and no validation: a missing key is simply absent from the state, and a wrong type gets through unchanged.
  - `subtotal` and `total` (lines 29–30) are outputs. The caller does not pass them. They show up in the state only after a node writes them.
  - `tax_rate` and `currency` (lines 27–28) are inputs the caller must pass. A `TypedDict` cannot hold a default value, so [`TYPED_DICT_EXTRAS`](../src/l2_1_state_schemas/__main__.py#L10) exists only for this graph.
- [`compute_subtotal`](../src/l2_1_state_schemas/typed_dict_order.py#L37-L40) receives the state as a dict, so it reads keys with `state["quantity"]`. It returns only `subtotal`. LangGraph merges that one key into the state, and the other keys stay as they were.
- [`apply_tax`](../src/l2_1_state_schemas/typed_dict_order.py#L43-L46) reads `subtotal`, which exists because the edge on line 60 runs this node after `compute_subtotal`. If the caller left out `tax_rate`, line 46 raises `KeyError` inside the node. Nothing checked the input earlier, so this is the first place the mistake shows up. [`test_typed_dict_missing_key_raises_key_error`](../tests/test_state_schemas.py#L77-L80) checks exactly this.
- [`build_graph`](../src/l2_1_state_schemas/typed_dict_order.py#L53-L62) is the lesson 1.1 wiring. Line 56 is the only line that differs between the three modules: the schema class passed to `StateGraph`. Lessons 2.2–2.4 grow this module, so it is kept flat.

## [dataclass_order.py](../src/l2_1_state_schemas/dataclass_order.py)

The same graph with a `@dataclass` schema. This adds defaults but no type checks.

- [`OrderData`](../src/l2_1_state_schemas/dataclass_order.py#L14-L28) declares the same seven fields. Lines 25–28 give defaults to the four optional ones. LangGraph still keeps one channel per field, but before each node runs it builds an `OrderData` from the stored values. A field that no one has written yet gets its default at that point. That is why the caller can leave out `tax_rate` and `currency`.
  - A dataclass does not check the types of the values passed to it. `quantity=-2` or `quantity="3"` are stored as they are. See the bad-input section below.
  - The defaults exist only in the instance the node receives. They are not written back to the state. This matters for the v1 output, as the coercion section of `__main__.py` shows.
- [`compute_subtotal`](../src/l2_1_state_schemas/dataclass_order.py#L35-L39) and [`apply_tax`](../src/l2_1_state_schemas/dataclass_order.py#L42-L45) do the same work as in the TypedDict version. The nodes read attributes (`state.quantity`) but still return a plain dict with only the changed key. LangGraph treats a returned dict as a partial update for every schema type. A node does not have to build a new `OrderData`.
- On line 45, `state.tax_rate` is `0.2` from the default on line 25 when the caller did not pass it.
- [`build_graph`](../src/l2_1_state_schemas/dataclass_order.py#L51-L59): only line 53 differs from the TypedDict module.

## [pydantic_order.py](../src/l2_1_state_schemas/pydantic_order.py)

The same graph with a Pydantic `BaseModel`. This adds validation and type conversion on top of the defaults.

- [`OrderModel`](../src/l2_1_state_schemas/pydantic_order.py#L14-L24) has the same defaults as `OrderData`. Lines 19–20 add `Field(gt=0)` to `quantity` and `unit_price`. To build each node's input, LangGraph calls `OrderModel(**state)`, and that is when Pydantic validates the values. A bad input value therefore fails before the first node runs, and the error is a `pydantic.ValidationError`, not an error from inside a node.
  - Pydantic's default ("lax") mode also converts values. With `quantity: int`, the string `"3"` becomes the integer `3` in the model instance.
  - Validation happens when a node's input is built, not when a node's update is written. A node can return an invalid value, and it is stored. It fails only when the next node's input is built, or when `version="v2"` converts the output. If it is the last node, nothing fails in v1. [`test_node_updates_not_validated_on_write`](../tests/test_state_schemas.py#L59-L74) shows this with a node that writes `quantity=-1`.
- [`compute_subtotal`](../src/l2_1_state_schemas/pydantic_order.py#L31-L35): `state` is a validated `OrderModel`, so on line 35 `state.quantity` is already an `int`. That is why the string input in section (c) still gives the right subtotal of `28.5`.
- [`apply_tax`](../src/l2_1_state_schemas/pydantic_order.py#L38-L40) is the same as in the dataclass version.
- [`build_graph`](../src/l2_1_state_schemas/pydantic_order.py#L46-L54): only line 48 differs.

## [\_\_main\_\_.py](../src/l2_1_state_schemas/__main__.py)

The entry point. [`main`](../src/l2_1_state_schemas/__main__.py#L13-L71) builds the three graphs once (lines 15–17) and runs four sections on them.

- [`ORDER`](../src/l2_1_state_schemas/__main__.py#L8) is the shared input with only the three required fields. The dataclass and Pydantic graphs accept it as it is. The TypedDict graph gets `{**ORDER, **TYPED_DICT_EXTRAS}` (line 21).
- **Same order, three schemas** (lines 19–26): all three print `34.2`. A plain `invoke()` uses `version="v1"` and returns a dict of the stored channel values, whatever the schema type. That is why `result['total']` works even for the dataclass and Pydantic graphs.
- **Bad input** ([lines 28–44](../src/l2_1_state_schemas/__main__.py#L28-L44)): with `quantity=-2`, the TypedDict and dataclass graphs (lines 32–35) compute `-22.8` without any complaint, because neither schema checks values. The Pydantic graph raises on line 39 before `compute_subtotal` runs. `exc.errors()` returns a list of dicts, one per failed field. Line 42 joins the `loc` tuple (here `("quantity",)`) so that the output reads `quantity: Input should be greater than 0`.
- **Coercion** ([lines 46–54](../src/l2_1_state_schemas/__main__.py#L46-L54)): the Pydantic graph gets `quantity="3"`. Line 50 prints `'3'`, a string. Conversion to `int` happened only in the `OrderModel` instances that the nodes received. The channel still holds the raw value from the input. Line 53 prints the keys, and `tax_rate` and `currency` are missing: their defaults lived only in the model instances, and no node returned them, so they never reached the state.
- **Typed output** ([lines 56–71](../src/l2_1_state_schemas/__main__.py#L56-L71)): `invoke(order, version="v2")` on line 67 returns a `GraphOutput` instead of a dict. Its `.value` is built from the final channel values by calling the schema class, so it is an `OrderData` or an `OrderModel`. For the Pydantic graph this second construction converts `"3"` to `3` and fills in the default `tax_rate` and `currency`. You can see this in the output, unlike the v1 result above.
  - Lines 61–62 give the two graphs different inputs. The dataclass graph gets the integer `ORDER`, because a dataclass would not convert `"3"`: `"3" * 9.5` would raise `TypeError` in `compute_subtotal`. Only the Pydantic graph gets the string input from the coercion section. The `OrderData` value also shows the default `tax_rate` and `currency`, because v2 builds the dataclass from the stored values too.
  - Line 70 prints `.interrupts`, an empty tuple here because nothing paused the graph. Interrupts come later in the course.
  - The code reads only `.value` and `.interrupts`. Dict access such as `out["total"]` on a `GraphOutput` still works but has been deprecated since LangGraph 1.1.
  - For a TypedDict schema v2 has no class to build, so `.value` stays a plain dict. [`test_v2_output_types`](../tests/test_state_schemas.py#L49-L56) checks both cases.

## [test_state_schemas.py](../tests/test_state_schemas.py)

The tests repeat the live run's claims as assertions and add the two cases `main` does not show.

- [`test_pydantic_rejects_zero_quantity_dataclass_does_not`](../tests/test_state_schemas.py#L25-L31) uses `quantity=0`, the edge case for `gt=0`. The dataclass graph returns `total == 0.0` (line 31).
- [`test_pydantic_coercion_v1_vs_v2`](../tests/test_state_schemas.py#L34-L46) puts the v1 and v2 results for the string quantity side by side.
- [`test_node_updates_not_validated_on_write`](../tests/test_state_schemas.py#L59-L74) builds its own one-node `StateGraph(OrderModel)` in the test. Line 72 shows that the invalid `-1` is stored and returned by v1, and line 74 shows that v2 rejects it when it builds the output model.

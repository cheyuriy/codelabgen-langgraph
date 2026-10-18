# 2.3 Input, Output and Private Schemas — code walkthrough

The order pipeline from 2.2 now has a narrow public interface. A caller sends only the cart and pricing settings, and gets back only a receipt. The `subtotal` moves into a private schema that only two nodes use. The program prints the interface, runs Ada's and Bob's orders, and then streams the node updates to show the private `subtotal` moving between nodes. Run it with `./run.sh 2.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since 2.2

- [`OrderDict`](../src/l2_3_input_output_schemas/typed_dict_order.py#L57-L68) loses `subtotal` (line 65 says where it went). The other six keys and their reducers are unchanged.
- New: [`OrderInput` and `OrderOutput`](../src/l2_3_input_output_schemas/typed_dict_order.py#L74-L96), the public input and the receipt.
- New: the private [`PricingState`](../src/l2_3_input_output_schemas/typed_dict_order.py#L100-L108) with `subtotal`, `tax_rate` and `currency`.
- [`apply_tax`](../src/l2_3_input_output_schemas/typed_dict_order.py#L163-L166) changes only its parameter hint, from `OrderDict` to `PricingState`. Its body is the same.
- [`build_graph`](../src/l2_3_input_output_schemas/typed_dict_order.py#L173-L188) passes `input_schema=OrderInput` and `output_schema=OrderOutput` to `StateGraph` (line 178). The nodes and edges are unchanged.
- `LineItem`, `merge_items`, `check_stock`, `apply_bundle`, `compute_subtotal` and the constants are the same as in 2.2. `compute_subtotal` only gains a comment (line 156).
- [`__main__.py`](../src/l2_3_input_output_schemas/__main__.py) has four new sections in place of 2.2's three. The direct `merge_items` calls are gone. [test_schemas.py](../tests/test_schemas.py) replaces `test_reducers.py`.
- The results stay the same: Ada pays `16.8 EUR`, Bob pays `7.2 EUR`.

## [typed_dict_order.py](../src/l2_3_input_output_schemas/typed_dict_order.py)

The whole graph: four schemas, four nodes and the wiring. The [module docstring](../src/l2_3_input_output_schemas/typed_dict_order.py#L1-L11) gives one line per schema, which is a good map to keep open while you read the file.

- [`merge_items`](../src/l2_3_input_output_schemas/typed_dict_order.py#L36-L50), [`LineItem`](../src/l2_3_input_output_schemas/typed_dict_order.py#L24-L29) and the constants are explained in the [2.2 walkthrough](../../2.2-reducers/docs/readalong.md).

### The state schema

- [`OrderDict`](../src/l2_3_input_output_schemas/typed_dict_order.py#L57-L68) is still the graph's state schema: the first argument of `StateGraph`. `StateGraph` registers it first, so it decides each key's channel: `items` gets `merge_items` (line 62), `log` gets `operator.add` (line 68), and the other keys keep the last value written.
- `subtotal` is no longer here. If it were, it would also be in the default output, and any node could read it. Now it comes from `PricingState`, as explained below.

### The input and output schemas

- [`OrderInput`](../src/l2_3_input_output_schemas/typed_dict_order.py#L77-L83) lists the four keys a caller sends. [`OrderOutput`](../src/l2_3_input_output_schemas/typed_dict_order.py#L86-L93) lists the five keys of the receipt. Neither one contains `subtotal`, and the receipt has no `tax_rate`.
- Lines 81 and 93 use plain annotations for `items` and `log`, on purpose. A key is one channel for the whole graph, not one per schema. When `StateGraph` registers a second schema, it skips a key that already has a channel if the new annotation is a plain type. That is why the input still goes through `merge_items`: two `PEN` lines in the input become one ([`test_input_still_goes_through_reducer`](../tests/test_schemas.py#L79-L84)).
- If line 81 named a *different* reducer, for example `Annotated[list[LineItem], operator.add]`, `StateGraph(...)` would raise `ValueError: Channel 'items' already exists with a different type`. Another schema may repeat a key, but it may not give it a different reducer.
- These two classes are used only as arguments to `StateGraph`. No node has them as a hint.

### The private schema

- [`PricingState`](../src/l2_3_input_output_schemas/typed_dict_order.py#L100-L108) is not passed to `StateGraph` at all. It reaches the graph through the hint of `apply_tax` (see below). `tax_rate` and `currency` are already channels from `OrderDict`, so the only new channel it adds is `subtotal` (line 106).
- "Private" is not an access control. Any node can write to `subtotal`, and a node typed with `PricingState` can read it. It is private because it is in neither `OrderInput` nor `OrderOutput`, so no caller can send it or receive it.

### The nodes

- [`check_stock`](../src/l2_3_input_output_schemas/typed_dict_order.py#L115-L128) and [`apply_bundle`](../src/l2_3_input_output_schemas/typed_dict_order.py#L135-L145) are unchanged from 2.2. Their hint is `OrderDict`, so each one receives all the `OrderDict` keys.
- [`compute_subtotal`](../src/l2_3_input_output_schemas/typed_dict_order.py#L152-L157) still reads `OrderDict`, which has no `subtotal`, and still returns `{"subtotal": ..., "log": [...]}` on line 157. This works because a node's hint controls only what the node *reads*. A node may write to any channel of the graph. Writing to a key that has no channel would be dropped without an error, which is what happens if `PricingState` is never registered.
- [`apply_tax`](../src/l2_3_input_output_schemas/typed_dict_order.py#L163-L166) is where the private schema enters the graph. When `add_node` gets a function without an explicit `input_schema=`, it reads the type hint of the first parameter. If that hint is a class with annotations, it becomes the node's input schema, and its keys are registered as channels. In LangGraph 1.2.16 this is in `StateGraph.add_node`, in `langgraph/graph/state.py`, around lines 813–835 and 922–924. Return annotations are not used for this.
  - So at run time `apply_tax` receives a dict with only `subtotal`, `tax_rate` and `currency`. Line 166 can read `state["currency"]`, but `state["customer"]` would raise `KeyError`, even though `customer` is in the graph's state.
  - If you remove the hint (`def apply_tax(state)`), the node falls back to `OrderDict`, and `PricingState` is never registered. Then the `subtotal` channel does not exist, the write on line 157 is dropped, and line 165 raises `KeyError: 'subtotal'`.

### The wiring

- [`build_graph`](../src/l2_3_input_output_schemas/typed_dict_order.py#L173-L188): line 178 registers three schemas in this order: `OrderDict`, then `OrderInput`, then `OrderOutput`. Then each `add_node` call (lines 179–182) registers its node's input schema. Only line 182 adds something new: `subtotal`. That is why `subtotal` comes last in the channels line of the live run.
  - `input_schema=OrderInput` decides which keys `START` writes into the channels. Other keys in the `invoke` input are dropped without an error.
  - `output_schema=OrderOutput` decides which channels `invoke` reads at the end and returns, as a plain dict.
  - Without these two arguments, both would default to `OrderDict`. The receipt would then include `tax_rate`, and Bob's `"web: checkout"` would reach the log. `subtotal` would still stay hidden, because it is not in `OrderDict`.
  - The keyword names are `input_schema` and `output_schema`. The older `input=` and `output=` still work but are deprecated.

## [\_\_main\_\_.py](../src/l2_3_input_output_schemas/__main__.py)

The entry point. [`main`](../src/l2_3_input_output_schemas/__main__.py#L21-L77) builds the graph once (line 23) and runs four sections. [`ADA_CART`, `BOB_CART`](../src/l2_3_input_output_schemas/__main__.py#L5-L13) and [`fmt_items`](../src/l2_3_input_output_schemas/__main__.py#L16-L18) are the same as in 2.2.

- **The public interface** ([lines 26–32](../src/l2_3_input_output_schemas/__main__.py#L26-L32)): `get_input_jsonschema()` and `get_output_jsonschema()` on the compiled graph build JSON Schemas from `OrderInput` and `OrderOutput`. A server or a client would use these to describe the graph's API. Line 32 reads `graph.builder.channels`, the builder's dict of all channels. It is the only line that shows `subtotal`. The key lists are printed in definition order, not sorted.
- **Ada** ([lines 36–46](../src/l2_3_input_output_schemas/__main__.py#L36-L46)): the input on line 37 has exactly the `OrderInput` keys. Line 40 prints the keys of the result. They are the five `OrderOutput` keys, so `tax_rate` went in but does not come back. The cart, the log and the total match 2.2.
- **Bob** ([lines 50–67](../src/l2_3_input_output_schemas/__main__.py#L50-L67)): the input has two extra keys, `log` (line 56) and `subtotal` (line 57). In 2.2, `log` in the input was appended to, and Bob's log had five lines. Now `START` writes only `OrderInput` keys, so both extras are dropped and nothing is reported. The log has four lines and starts with `check_stock`. The injected `subtotal=0.0` has no effect either: the total is still `7.2 EUR`. Silent filtering is convenient, but a typo in a key name is lost without an error.
- **Inside the graph** ([lines 71–77](../src/l2_3_input_output_schemas/__main__.py#L71-L77)): `stream_mode="updates"` yields one chunk per node with what that node returned, before the output schema is applied. Line 76 prints the keys of each update, so `compute_subtotal writes: subtotal, log` shows the private value. Line 77 runs a fresh `invoke` and checks that `subtotal` is not in the receipt. Note that `ada_order` is reused here: the graph has no checkpointer, so each run starts from empty channels.

## [test_schemas.py](../tests/test_schemas.py)

The tests check the live run's results and add two checks that `main` does not print.

- [`test_ada_receipt_has_only_output_keys`](../tests/test_schemas.py#L23-L34) compares the result keys as a set (line 26) and the full log with 2.2's four lines.
- [`test_bob_extra_input_keys_are_dropped`](../tests/test_schemas.py#L37-L50): line 49 (four log lines) and line 50 (the first line is `check_stock`) together prove that the input `log` was dropped, not appended.
- [`test_interface_and_channels`](../tests/test_schemas.py#L53-L64) checks the two JSON Schemas and that `subtotal` is a channel but not in either one. Lines 63–64 check `builder.nodes[...].input_schema`, which shows the hint inference directly: `PricingState` for `apply_tax`, `OrderDict` for `compute_subtotal`.
- [`test_subtotal_travels_inside_the_graph`](../tests/test_schemas.py#L67-L76) compares the whole `compute_subtotal` update (line 72), including `subtotal: 14.0`, and then checks that the receipt does not have it.
- [`test_input_still_goes_through_reducer`](../tests/test_schemas.py#L79-L84) shows that the plain annotation in `OrderInput` does not replace the reducer: the two `PEN` lines merge into the later one.

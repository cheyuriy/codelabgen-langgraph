# 2.2 Reducers: How Updates Are Combined — code walkthrough

The program runs two orders through a four-node pipeline: `check_stock`, `apply_bundle`, `compute_subtotal`, `apply_tax`. Ada's order shows a custom reducer updating the cart line by line. Bob's order shows `Overwrite` replacing the cart outright. The last part calls the reducer by hand as an ordinary function. Run it with `./run.sh 2.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since 2.1

- `dataclass_order.py`, `pydantic_order.py` and their tests are gone. Comparing schemas was the topic of 2.1. From here on only the TypedDict pipeline grows. [pyproject.toml](../pyproject.toml) now pins only `langgraph==1.2.16`, because nothing imports `pydantic` directly any more.
- [`OrderDict`](../src/l2_2_reducers/typed_dict_order.py#L54-L65) no longer has `quantity` and `unit_price`. It has a cart, `items`, with the custom reducer [`merge_items`](../src/l2_2_reducers/typed_dict_order.py#L33-L47) (line 59), and an audit log, `log`, with `operator.add` (line 65). The other five keys are unchanged.
- New: the [`LineItem`](../src/l2_2_reducers/typed_dict_order.py#L21-L26) type and the constants `STOCK`, `STARTER_KIT` and `KIT_ITEM` ([lines 17–29](../src/l2_2_reducers/typed_dict_order.py#L17-L29)).
- Two new nodes run before the 2.1 nodes: [`check_stock`](../src/l2_2_reducers/typed_dict_order.py#L72-L85) and [`apply_bundle`](../src/l2_2_reducers/typed_dict_order.py#L92-L102).
- [`compute_subtotal`](../src/l2_2_reducers/typed_dict_order.py#L109-L113) now sums over the cart and rounds. Every node, [`apply_tax`](../src/l2_2_reducers/typed_dict_order.py#L116-L119) included, also returns one log line.
- [`build_graph`](../src/l2_2_reducers/typed_dict_order.py#L126-L140) registers four nodes instead of two and chains them in the order above.
- [`__main__.py`](../src/l2_2_reducers/__main__.py) has three new sections in place of the four schema sections. [test_reducers.py](../tests/test_reducers.py) replaces `test_state_schemas.py`.

## [typed_dict_order.py](../src/l2_2_reducers/typed_dict_order.py)

The whole graph: the state with its reducers, the four nodes and the wiring.

- [`STOCK`, `STARTER_KIT`](../src/l2_2_reducers/typed_dict_order.py#L17-L18) and [`KIT_ITEM`](../src/l2_2_reducers/typed_dict_order.py#L29) are plain module data. They are not part of the state, so no reducer applies to them.
- [`LineItem`](../src/l2_2_reducers/typed_dict_order.py#L21-L26) is a type hint only, like `OrderDict` in 2.1. At run time a cart line is a plain dict, and LangGraph does not look inside it.

### The reducer

- [`merge_items`](../src/l2_2_reducers/typed_dict_order.py#L33-L47) is a reducer, which is just a function of two arguments. LangGraph calls it as `merge_items(stored_value, update)` each time something writes to `items`, and stores whatever it returns. The function has no LangGraph imports, which is why `__main__.py` and the tests can call it directly.
  - Line 41 builds a new dict from `current`. Line 47 returns a new list. The stored list is never changed in place. If the reducer mutated `current`, the value LangGraph already holds would change behind its back. [`test_merge_items_upsert`](../tests/test_reducers.py#L48-L58) checks that `current` stays the same (line 56).
  - Line 44 handles `quantity <= 0` as "remove this line". `pop(..., None)` does nothing for an sku that is not in the cart, so removing a missing line is not an error.
  - Line 46 relies on the order of dict insertion: assigning to an existing key keeps its position, and a new key goes to the end. So a replaced line stays where it was, and a new line is appended.
  - The reducer also runs on the `invoke` input. A reducer key's channel starts empty (`[]` for a list), and the input is written into it like any node update, so the input becomes `merge_items([], input_items)`. That is why two `PEN` lines in the input end up as one ([`test_invoke_input_goes_through_reducer`](../tests/test_reducers.py#L61-L66)).

### The state

- [`OrderDict`](../src/l2_2_reducers/typed_dict_order.py#L54-L65) is where each key gets its rule for combining updates. `StateGraph` reads the `Annotated[...]` metadata. A key with a reducer gets a channel that calls the reducer on each write (in LangGraph's internals, a `BinaryOperatorAggregate`). A key without one gets a channel that keeps the last value written.
  - Line 59: `items` uses `merge_items`, so a node can send only the lines it wants to change.
  - Lines 57 and 60–63: `customer`, `tax_rate`, `currency`, `subtotal` and `total` have no reducer. A write replaces the value. That is right for `subtotal` and `total`, which are computed once per run.
  - Line 65: `log` uses `operator.add`, which for lists is `stored + update`. Each node's line is appended to the end. The update must be a list too: `operator.add` cannot add a `str` to a list.

### The nodes

All four nodes return a partial update with only the keys they change, as in 2.1. The difference now is that LangGraph sends `items` and `log` through their reducers before storing them.

- [`check_stock`](../src/l2_2_reducers/typed_dict_order.py#L72-L85) collects only the lines above stock, with the quantity lowered to what is available (line 78). It does not return the whole cart: `merge_items` replaces those lines and keeps the rest. For `MUG` the stock is `0`, so the capped line has quantity `0`, and the reducer removes it. A node that writes `0` to delete something works only because of how `merge_items` is written. The reducer and the nodes have to agree on what an update means.
  - Line 81: when everything is in stock, the node still returns `"items": []`. `merge_items(cart, [])` gives back the same lines, so the cart does not change. Leaving `items` out of the dict would have the same effect.
  - Line 82 records the old quantities before the update. Inside the node, `state["items"]` is still the cart from before this step. The node's return value is applied only after the node finishes.
  - Line 85 returns the log line in a one-element list, as `operator.add` needs.
- [`apply_bundle`](../src/l2_2_reducers/typed_dict_order.py#L92-L102) compares the cart, as `{sku: quantity}`, with `STARTER_KIT` (line 95). If they match, it has to replace the whole cart with one kit line. A plain `[KIT_ITEM]` would go through `merge_items` and be appended next to `PEN` and `NOTEBOOK`, which is the three-line result printed in the last section of the live run. `Overwrite([KIT_ITEM])` on line 100 tells the channel to store the wrapped value as it is, without calling the reducer. It applies only to `items`: the `log` line in the same return still goes through `operator.add`.
  - When there is no bundle (line 96), the node returns only `log`, and `items` is not touched.
- [`compute_subtotal`](../src/l2_2_reducers/typed_dict_order.py#L109-L113) reads the cart as it is after the first two nodes. For Ada that is `PEN x4, NOTEBOOK x2` (`14.0`). For Bob it is the kit alone (`6.0`). `round(..., 2)` on line 112 avoids float noise in the log line.
- [`apply_tax`](../src/l2_2_reducers/typed_dict_order.py#L116-L119) computes `total` as in 2.1 and adds the currency to its log line. `total` is a plain key, so this write replaces it.

### The wiring

- [`build_graph`](../src/l2_2_reducers/typed_dict_order.py#L126-L140): line 130 is where the reducers take effect. `StateGraph(OrderDict)` builds the channels from the annotations, and nothing else in the wiring mentions reducers. The edges on lines 135–139 make a straight line, so exactly one node writes per step. A reducer on `log` is needed here to keep earlier lines, not to resolve concurrent writes. The test file shows the concurrent case.

## [\_\_main\_\_.py](../src/l2_2_reducers/__main__.py)

The entry point. [`main`](../src/l2_2_reducers/__main__.py#L26-L75) builds the graph once (line 28) and runs three sections.

- [`ADA_CART` and `BOB_CART`](../src/l2_2_reducers/__main__.py#L10-L18) are module constants. Both are passed to `invoke` and later to `merge_items` directly. This is safe because the reducer never mutates the list it receives, so the "cart in" lines print the original carts.
- [`fmt_items`](../src/l2_2_reducers/__main__.py#L21-L23) only formats a cart for printing.
- **Ada** ([lines 31–39](../src/l2_2_reducers/__main__.py#L31-L39)): the input on line 32 has no `subtotal`, `total` or `log`. The `log` channel starts as an empty list, so the four node lines are all it holds at the end. "cart out" shows `NOTEBOOK` lowered to 2 in its original place, and `MUG` gone.
- **Bob** ([lines 43–58](../src/l2_2_reducers/__main__.py#L43-L58)): line 50 passes `log=["web: checkout"]` in the input. The input goes through `operator.add` like any update (`[] + ["web: checkout"]`), and every node line is appended after it, so the log has five lines with the input line first. The cart matches `STARTER_KIT` exactly, so "cart out" is `STARTER-KIT x1` and the total is `7.2 EUR`.
- **Reducers are plain functions** ([lines 62–74](../src/l2_2_reducers/__main__.py#L62-L74)): line 69 calls `merge_items` with Ada's cart and the same kind of update `check_stock` returns. The result matches the graph's "cart out" from the first section. Line 71 does what `apply_bundle` would do without `Overwrite`, and the result has three lines. Calling the reducer alone, without a graph, shows the bug that `Overwrite` prevents.

## [test_reducers.py](../tests/test_reducers.py)

The tests check the live run's results and add two cases that `main` does not show.

- [`test_ada_stock_check_through_merge_items`](../tests/test_reducers.py#L23-L35) and [`test_bob_bundle_overwrites_cart`](../tests/test_reducers.py#L38-L45) check the two orders. Line 27 compares whole lists, so it also checks the order of the cart lines.
- [`test_merge_items_upsert`](../tests/test_reducers.py#L48-L58) covers the three cases of the reducer in one call: replace (`NOTEBOOK2`), append (`cup`) and remove (`mug0`). Line 51 keeps a deep copy to prove that `current` was not mutated.
- [`test_invoke_input_goes_through_reducer`](../tests/test_reducers.py#L61-L66) passes two `PEN` lines as input. The reducer keeps the later one, before any node runs.
- [`test_parallel_writes_need_a_reducer`](../tests/test_reducers.py#L91-L96) shows the other reason reducers exist. [`_fan_out`](../tests/test_reducers.py#L81-L88) wires two nodes from `START`, so they run in the same step and both write `log`. With [`PlainLog`](../tests/test_reducers.py#L69-L72), a key without a reducer cannot take two values in one step, and `invoke` raises `InvalidUpdateError` (line 94). With [`AddedLog`](../tests/test_reducers.py#L75-L78), `operator.add` combines both writes. Line 96 sorts the result because the test does not rely on which parallel write is applied first.

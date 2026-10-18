# 2.4 Runtime Context: Configuration Outside the State — code walkthrough

The order pipeline from 2.3 no longer carries the shop settings in its state. `tax_rate` and `currency` move into a run context, `ShopContext`, which the caller passes with each `invoke`. The program prints the interface, prices Ada's cart for an EU shop and a US shop with one compiled graph, shows that old-style settings in the input are ignored, and streams the node updates. Run it with `./run.sh 2.4` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since 2.3

- New: [`ShopContext`](../src/l2_4_runtime_context/typed_dict_order.py#L115-L128), a frozen dataclass with `tax_rate` and `currency`, in its own `shop_context` region. Two new imports: `dataclass` (line 19) and `Runtime` from `langgraph.runtime` (line 24).
- `tax_rate` and `currency` are gone from [`OrderDict`](../src/l2_4_runtime_context/typed_dict_order.py#L64-L74) (line 70 says where they went), [`OrderInput`](../src/l2_4_runtime_context/typed_dict_order.py#L83-L87) and [`PricingState`](../src/l2_4_runtime_context/typed_dict_order.py#L103-L109). [`OrderOutput`](../src/l2_4_runtime_context/typed_dict_order.py#L90-L96) loses `currency`.
- [`apply_tax`](../src/l2_4_runtime_context/typed_dict_order.py#L184-L188) gets a second parameter, `runtime: Runtime[ShopContext]`, and reads both settings from `runtime.context` instead of `state`.
- [`build_graph`](../src/l2_4_runtime_context/typed_dict_order.py#L195-L217) passes `context_schema=ShopContext` (line 206). Nodes and edges are unchanged.
- The [module docstring](../src/l2_4_runtime_context/typed_dict_order.py#L1-L16) adds `ShopContext` and the difference between state and context.
- `LineItem`, `merge_items`, `check_stock`, `apply_bundle`, `compute_subtotal`, `KIT_ITEM`, `STOCK` and `STARTER_KIT` are the same as in 2.3.
- [`__main__.py`](../src/l2_4_runtime_context/__main__.py) adds `EU_SHOP` and `US_SHOP`. The interface section prints a context line, the Ada section becomes "One graph, two shops", the Bob section sends 2.3-style settings in the input, and the stream passes `context=EU_SHOP`. [test_context.py](../tests/test_context.py) replaces `test_schemas.py`.
- The cart numbers stay the same: subtotal `14.0` for Ada, `6.0` for Bob. With the EU context the totals are still `16.8 EUR` and `7.2 EUR`.

## [typed_dict_order.py](../src/l2_4_runtime_context/typed_dict_order.py)

The whole graph: four schemas, one context, four nodes and the wiring. [`merge_items`](../src/l2_4_runtime_context/typed_dict_order.py#L42-L60), `LineItem` and the constants are explained in the [2.2 walkthrough](../../2.2-reducers/docs/readalong.md). The input, output and private schemas are explained in the [2.3 walkthrough](../../2.3-input-output-schemas/docs/readalong.md).

### The schemas

- [`OrderDict`](../src/l2_4_runtime_context/typed_dict_order.py#L64-L74) now has four keys: `customer`, `items`, `total`, `log`. Everything in it is a channel, so a value here is something nodes change and the graph can return. The shop settings don't change during a run, so they don't belong here.
- [`OrderInput`](../src/l2_4_runtime_context/typed_dict_order.py#L83-L87) is just the cart. Because `START` writes only these keys, a caller who still sends `tax_rate` gets no error, and the value is simply dropped. The Bob section shows this.
- [`OrderOutput`](../src/l2_4_runtime_context/typed_dict_order.py#L90-L96) has no `currency` any more. The caller chose the currency when it passed the context, so the receipt doesn't need to repeat it.
- [`PricingState`](../src/l2_4_runtime_context/typed_dict_order.py#L103-L109) keeps only `subtotal`. In 2.3 `apply_tax` read all three of its values from the state. Now it reads one from the state and two from the context.

### The context

- [`ShopContext`](../src/l2_4_runtime_context/typed_dict_order.py#L120-L125) is a plain Python dataclass, not a `TypedDict`. LangGraph never makes channels from it. It only uses it to describe and check what a caller passes as `context=`.
- No defaults (lines 124–125): a context dict with a misspelled key, such as `{"tax": 0.2, ...}`, fails before the run with `TypeError: ShopContext.__init__() got an unexpected keyword argument 'tax'`. With a default, the order would be priced with the fallback and nobody would notice.
- `frozen=True` (line 120): the same context object is shared by every node in the run. If a node tries `runtime.context.tax_rate = 0.0`, it gets `dataclasses.FrozenInstanceError`. A value that nodes need to change belongs in the state.

### The nodes

- [`check_stock`](../src/l2_4_runtime_context/typed_dict_order.py#L132-L145), [`apply_bundle`](../src/l2_4_runtime_context/typed_dict_order.py#L152-L162) and [`compute_subtotal`](../src/l2_4_runtime_context/typed_dict_order.py#L169-L174) don't take a `runtime` parameter, and that's fine. Only nodes that ask for the runtime get it, so the context is visible only where it's needed.
- [`apply_tax`](../src/l2_4_runtime_context/typed_dict_order.py#L184-L188) is where the context is used.
  - When `add_node` wraps the function, LangGraph looks at its parameter *names*. A parameter called `runtime` is filled with a `Runtime` object on every call. The `Runtime[ShopContext]` annotation does nothing at run time: if you rename the parameter to `rt`, the call fails with `TypeError: apply_tax() missing 1 required positional argument: 'rt'`. The annotation is there for you and for the type checker, which then knows that `runtime.context.tax_rate` is a `float`.
  - The first parameter still works as in 2.3: its hint `PricingState` makes the node's input schema, so `state` has only `subtotal`.
  - `runtime.context` (lines 187–188) is the `ShopContext` given to this call of `invoke` or `stream`. The `Runtime` object also carries other run-level things, such as the store and the stream writer, which this lesson doesn't use.
  - If the caller passes no context, `runtime.context` is `None`, and line 187 raises `AttributeError: 'NoneType' object has no attribute 'tax_rate'`. LangGraph doesn't create a `ShopContext` for you, even if its fields had defaults.

### The wiring

- [`build_graph`](../src/l2_4_runtime_context/typed_dict_order.py#L195-L217): line 206 passes `context_schema=ShopContext`. This adds no channels (the channels line of the live run shows only `customer, items, total, log, subtotal`). The compiled graph keeps the schema as `graph.context_schema`, uses it for `get_context_jsonschema()`, and uses it to turn a dict context into a `ShopContext`.
  - The settings are not baked into the compiled graph. That's why one `build_graph()` call can serve both shops.
  - Older code declares its settings with `config_schema=` and reads them from `config["configurable"]`. `config_schema=` is deprecated: the context API replaced it in 0.6, and 1.2.16 warns with `LangGraphDeprecatedSinceV10` ("to be removed in V2.0"). It still works in 1.2.16 and maps to `context_schema`, with a warning that you only see when you run Python with `-W default::DeprecationWarning`. `config["configurable"]` itself is not deprecated: LangGraph still uses it for its own keys, such as `thread_id`. What is outdated is putting your own settings there. Values put in `config["configurable"]` never reach `runtime.context`.

## [\_\_main\_\_.py](../src/l2_4_runtime_context/__main__.py)

The entry point. [`EU_SHOP` and `US_SHOP`](../src/l2_4_runtime_context/__main__.py#L14-L15) are two contexts made once at import time. Because they are frozen, it is safe to share them between runs. [`main`](../src/l2_4_runtime_context/__main__.py#L23-L81) builds the graph once (line 26), and `ada_order` (line 28) is now just the customer and the cart.

- **The public interface** ([lines 30–39](../src/l2_4_runtime_context/__main__.py#L30-L39)): line 35 is new. `get_context_jsonschema()` builds a JSON Schema from the dataclass, so a server or client can show which settings a run needs. Both fields are listed as required, because they have no defaults. Line 38 shows that `tax_rate` and `currency` are no longer channels.
- **One graph, two shops** ([lines 41–53](../src/l2_4_runtime_context/__main__.py#L41-L53)): line 43 runs once just to print the receipt keys: still the four `OrderOutput` keys, and nothing from the context. The loop then calls the same `graph` with a different `context=` each time (line 48). The cart and the subtotal are the same, and only the tax and the currency in the log differ: `16.8 EUR` and `15.12 USD`. Line 52 takes the currency from `shop`, because the receipt no longer has it.
- **Bob** ([lines 55–70](../src/l2_4_runtime_context/__main__.py#L55-L70)): line 58 is what a caller written for 2.3 would still send, with `tax_rate: 0.5` and `currency: "USD"` in the input. Line 60 is the context as a plain dict. On line 66 two things happen before any node runs: `START` drops the two extra input keys because they are not in `OrderInput`, and LangGraph turns the dict into `ShopContext(**dict)` because the context schema is a dataclass. The result is `7.2 EUR`, so the context won and the input values had no effect.
- **Inside the graph** ([lines 72–81](../src/l2_4_runtime_context/__main__.py#L72-L81)): the same as in 2.3, but `stream` on line 76 needs `context=` too, just like `invoke`. Without it, `apply_tax` would fail. The updates show that no node writes `tax_rate` or `currency`, and line 80 checks that `subtotal` stays out of the receipt.

## [test_context.py](../tests/test_context.py)

The tests check the live run's results and the failure without a context, which `main` doesn't show.

- [`test_one_graph_two_contexts`](../tests/test_context.py#L21-L30) uses one `graph` for both contexts and checks both totals and log lines.
- [`test_dict_context_is_coerced_and_input_settings_ignored`](../tests/test_context.py#L33-L39) uses a different dict context than `main` (`0.0`, `GBP`), so `6.0 GBP` on line 39 can only come from the context, not from the input's `0.5` and `USD`.
- [`test_context_is_not_state`](../tests/test_context.py#L42-L54) checks the context JSON Schema and its `required` list, that `graph.context_schema` is `ShopContext` (line 48), and that neither setting appears as a channel, an input key or an output key.
- [`test_no_context_no_default`](../tests/test_context.py#L57-L60) calls `invoke` without `context=` and expects the `AttributeError` from `apply_tax`.

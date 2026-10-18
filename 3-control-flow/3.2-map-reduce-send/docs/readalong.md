# 3.2 Map-Reduce with Send — code walkthrough

The order total is no longer part of the input. The graph computes it first: one `price_line` task per order line (the map step), then `sum_total` adds the results (the reduce step). After that, 3.1's three checks and `decide` run as before. The program shows Ada's order step by step, prints the decisions for Bob and Cleo with their computed totals, repeats 3.1's no-reducer demo, and times Dora's three-line order under different `max_concurrency` limits. Run it with `./run.sh 3.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 3.1

This lesson extends 3.1's "order-checks" example. The checks, the address branch, the join and `decide` have not changed. For those parts, see the [3.1 read-along](../../3.1-parallel-branches/docs/readalong.md).

- New file [pricing.py](../src/l3_2_map_reduce_send/pricing.py): the prices and the `price_line` map task.
- [`OrderBase`](../src/l3_2_map_reduce_send/checks.py#L25-L40) has a new key, `lines`, with a reducer (line 34). `total` is now written by `sum_total` (line 35).
- New [`route_lines`](../src/l3_2_map_reduce_send/checks.py#L69-L75) (the fan-out with `Send`) and [`sum_total`](../src/l3_2_map_reduce_send/checks.py#L82-L87) (the reduce step).
- [`build_graph`](../src/l3_2_map_reduce_send/checks.py#L158-L188) adds two nodes and a conditional edge from `START`. The three edges that started the checks now leave from `sum_total` instead of `START`.
- [\_\_main\_\_.py](../src/l3_2_map_reduce_send/__main__.py): the orders have no `total` any more, Bob's balance is 10.0, there is a new order `DORA`, and there is a new `max_concurrency` section.
- The tests moved to [test_map_reduce_send.py](../tests/test_map_reduce_send.py). The 3.1 tests are adapted, and there are new tests for the map-reduce part.

## [pricing.py](../src/l3_2_map_reduce_send/pricing.py)

The map task. It works on one line and knows nothing about orders, checks or the graph state.

- [`PRICES`](../src/l3_2_map_reduce_send/pricing.py#L6) holds the same three skus as `STOCK` in `checks.py`. Every demo order uses only these skus, so `price_line` can use a plain `PRICES[...]` lookup.
- [`PRICE_LOOKUP_S`](../src/l3_2_map_reduce_send/pricing.py#L10) is the fake delay of a price service. Without it, the three lookups would finish in microseconds and the `max_concurrency` section would print 0.0 s for every limit.
- [`PriceTask`](../src/l3_2_map_reduce_send/pricing.py#L14-L22) is what one `Send` carries: just `sku` and `qty`. It has a different shape from the order state on purpose. A Send task does not have to read the graph state; it gets its own input.
- [`LinePrice`](../src/l3_2_map_reduce_send/pricing.py#L25-L30) is one priced line, the element type of `lines` in the state.
- [`price_line`](../src/l3_2_map_reduce_send/pricing.py#L40-L46) is hinted with `PriceTask` (line 40). When a task starts from a `Send`, LangGraph passes the Send's `arg` dict to the node as its input, so `task["sku"]` works and there is no `items` or `balance` to see. Line 42 sleeps, line 43 computes the amount, and line 46 returns `lines` as a one-element list. As with `results` in 3.1, the `operator.add` reducer adds lists, so each task must return a list.

## [checks.py](../src/l3_2_map_reduce_send/checks.py)

The same file as in 3.1, with the map-reduce added in front of the checks.

- Line 8 imports `Send` from `langgraph.types`, the current place for it. Line 10 imports `LinePrice` (for the state) and `price_line` (for `build_graph`).

### The state

- [`lines`](../src/l3_2_map_reduce_send/checks.py#L34) in `OrderBase` is the key all `price_line` tasks write. For Ada, two tasks write it in super-step 1, so it needs a reducer for the same reason `results` needed one in 3.1: a key without a reducer accepts only one write per step. A one-line order like Cleo's would work without the reducer, and a two-line order would fail. That is why the reducer is there from the start.
- The reducer is in `OrderBase`, not in `OrderState`, so both [`OrderState`](../src/l3_2_map_reduce_send/checks.py#L43-L50) and [`NoReducerOrderState`](../src/l3_2_map_reduce_send/checks.py#L57-L60) get it. The no-reducer demo should still fail at `results` only, as in 3.1, not earlier at `lines`.
- [`total`](../src/l3_2_map_reduce_send/checks.py#L35) keeps its type. Only one node writes it, so it needs no reducer.

### The map: `route_lines`

- [`route_lines`](../src/l3_2_map_reduce_send/checks.py#L69-L75) is the function of a conditional edge, like the routing functions in lesson 1.2. The difference is the return value. Instead of node names, line 75 returns one `Send("price_line", {...})` per item. Each `Send` becomes its own task in the next super-step, with the payload as its input. A plain route (`return ["price_line"]`) would run `price_line` once with the whole order state, and it would fail with `KeyError: 'sku'`.
- The tasks follow `items` in its dict order: PEN, then NOTEBOOK for Ada (see the first lines of the live run).
- If `items` is empty, line 75 returns `[]`, no task is scheduled, and the run stops after the input with no `total` and no `decision`. LangGraph raises no error.
- The comment on lines 67–68 is the same trap as the one explained in 3.1 for the check nodes: the router's hint is registered as a schema too. If it used a different `lines` type, building the graph would fail with `ValueError: Channel 'lines' already exists with a different type`.

### The reduce: `sum_total`

- [`sum_total`](../src/l3_2_map_reduce_send/checks.py#L82-L87) reads all the lines the reducer has collected and writes `total`. It runs one step after the map, so by then every `price_line` write has been applied.
- `sum` does not care about the order of the lines. This matters because the stored order comes from LangGraph. On 1.2.16, `apply_writes` sorts a step's tasks by task path before applying their writes (`langgraph/pregel/_algo.py`, line 255). A Send task's path contains its position in the returned list, zero-padded to ten digits (`task_path_str`, line 1411), so the lines end up in Send-list order. That is how this version works, not a documented guarantee.
- `round(..., 2)` on line 87 keeps float sums like `0.1 + 0.2` from printing as `0.30000000000000004`.

### The checks and `decide`

[`check_stock`, `check_payment`](../src/l3_2_map_reduce_send/checks.py#L98-L115), [the address branch](../src/l3_2_map_reduce_send/checks.py#L122-L132) and [`decide`](../src/l3_2_map_reduce_send/checks.py#L139-L151) are the same as in 3.1. The only difference is where `total` comes from: line 112 in `check_payment` now reads the value `sum_total` wrote.

### The wiring

[`build_graph`](../src/l3_2_map_reduce_send/checks.py#L158-L188) is 3.1's graph with two nodes added in front.

- Lines 161–162 register `price_line` and `sum_total`. As usual, `add_node` reads each function's first-parameter hint: `PriceTask` for `price_line`, `OrderBase` for `sum_total`.
- Line 174 is the map. The third argument, `["price_line"]`, is the path map: the list of nodes the router may send to. The router only returns `Send` objects at run time, so without the list LangGraph cannot know in advance where they go. The run itself still works. The drawing does not: `get_graph()` walks the graph from `START` without running it, never reaches `price_line` or anything after it, and draws no edges at all, only a dotted `__start__ -.-> __end__` (see experiment 4 in the [notes](notes.md)). The list is used for the drawing only because the router returns Sends. If it also returned a node name, for example `"sum_total"` for an empty order, LangGraph would look that name up in this list, and the name would have to be added to it.
- Line 177 is the reduce. It is one plain edge, not a list edge as in 3.1's join. All `price_line` tasks are instances of the same node, so `sum_total` is triggered once in super-step 2, however many tasks ran in step 1.
- Lines 179–181 are 3.1's fan-out, now starting from `sum_total` instead of `START`. Because of this, `check_payment` always sees a `total`.
- Lines 183, 186 and 187 have not changed. Everything after the map-reduce is now two steps later. For Ada: step 1 `price_line` ×2, step 2 `sum_total`, step 3 the three checks, step 4 `check_address`, step 5 `decide`.
- If a `Send` names a node that does not exist, LangGraph logs `Ignoring unknown node name ... in pending sends` (`_algo.py`, line 977), drops the task and raises nothing.

## [\_\_main\_\_.py](../src/l3_2_map_reduce_send/__main__.py)

The entry point. The [orders](../src/l3_2_map_reduce_send/__main__.py#L10-L33) have no `total`. Bob's balance is 10.0, so he still fails the payment check against his computed total of 11.0. [`DORA`](../src/l3_2_map_reduce_send/__main__.py#L28-L33) has three lines and passes every check. She is used only for the timing section. [`main`](../src/l3_2_map_reduce_send/__main__.py#L36-L99) builds the graph once and runs four sections.

- **State after each super-step** ([lines 40–60](../src/l3_2_map_reduce_send/__main__.py#L40-L60)): lines 43–45 call `route_lines` directly, outside the graph, to print the `Send` objects it returns. It is a plain function, so this is a cheap way to look at the fan-out. Then the loop prints five steps. Line 51 uses `chunk.get("total", "-")` because `total` is missing until step 2. In the output, step 1 already has both lines and no total.
- **Decisions** ([lines 62–77](../src/l3_2_map_reduce_send/__main__.py#L62-L77)): lines 69–70 print the total and the stored lines it was computed from, for example `total 11.0 = PEN x2 3.0 + MUG x1 8.0`. The rest is as in 3.1.
- **No reducer** ([lines 79–87](../src/l3_2_map_reduce_send/__main__.py#L79-L87)): unchanged. It still fails at `results`. `lines` has its reducer in both schemas, so step 1 works and the error comes in step 3, when the checks run.
- **max_concurrency** ([lines 89–99](../src/l3_2_map_reduce_send/__main__.py#L89-L99)): `max_concurrency` is a run config key, passed as the second argument of `invoke` on line 97. Line 95 passes no key for `None`, so there is no limit. With no limit, Dora's three lookups run together (about 0.2 s). With 2, two run, then one (about 0.4 s). With 1, they run one after another (about 0.6 s). The sync executor uses the value as the size of its thread pool for the whole run, so it also limits super-step 3, where the three checks run. The times are wall-clock times and vary a little from run to run.

## [test_map_reduce_send.py](../tests/test_map_reduce_send.py)

- [`test_route_lines_sends_one_task_per_line`](../tests/test_map_reduce_send.py#L26-L31) and [`test_price_line_takes_a_price_task`](../tests/test_map_reduce_send.py#L34-L38) call the router and the map task as plain functions, without a graph. A `Send` has `node` and `arg` attributes you can compare.
- [`test_computed_totals_and_decisions`](../tests/test_map_reduce_send.py#L41-L62) sorts the skus on line 46, so it does not depend on the stored order.
- [`test_super_steps_on_1_2_16`](../tests/test_map_reduce_send.py#L65-L86) pins the five steps and the Send-list order of `lines` (lines 82–86: reversing Ada's items reverses the stored lines). Its docstring says this is 1.2.16 behaviour. It does not check the order of `stream_mode="updates"` chunks inside a step, because the two `price_line` updates can arrive in either order.
- [`test_sum_total_is_order_independent`](../tests/test_map_reduce_send.py#L89-L96) is the counterpart: the total is the same for both orders.
- [`test_max_concurrency_caps_map_tasks`](../tests/test_map_reduce_send.py#L99-L128) counts concurrent calls instead of measuring time, so a slow test machine cannot make it fail. Line 118 swaps `checks.price_line` before line 119 builds the graph. This works because `build_graph` looks up the name `price_line` in the `checks` module when it adds the node. The wrapper on line 105 keeps the `PriceTask` hint, so the node gets the same input schema as the real one.
- [`test_decide_is_order_independent`](../tests/test_map_reduce_send.py#L131-L143) adds `total` by hand on line 133, because it calls the nodes directly and no `sum_total` runs.
- [`test_waiting_edge_joins_once`](../tests/test_map_reduce_send.py#L151-L174) rebuilds the whole graph inline, map-reduce included, so the two-`decide` version starts the same way as the real one.
- [`test_no_reducer_raises`](../tests/test_map_reduce_send.py#L177-L181) checks that the error is still about `results`, not `lines`.

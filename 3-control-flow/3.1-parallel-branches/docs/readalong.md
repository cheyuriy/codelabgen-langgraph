# 3.1 Parallel Branches and Joins — code walkthrough

Before an order ships, three checks (stock, payment, address) run in parallel, and a `decide` node joins their results into "approved" or "on_hold". The program shows Ada's order step by step, prints the decisions for Bob and Cleo, and then runs the same graph without a reducer to show the error. Run it with `./run.sh 3.1` from the course root.
The concept itself is explained in the [notes](notes.md).

This is a new example, "order-checks". Lessons 3.2 and 3.3 build on it.

## [checks.py](../src/l3_1_parallel_branches/checks.py)

The whole graph: the state, five nodes and the wiring. Read it from top to bottom.

- [`STOCK` and `SHIPS_TO`](../src/l3_1_parallel_branches/checks.py#L9-L10) are the fixed data the checks compare against. These are the same products as in module 2. A sku that is not in `STOCK` counts as 0 in stock.

### The state

- [`CheckResult`](../src/l3_1_parallel_branches/checks.py#L14-L19) is one entry in `results`. Each check writes one of them. The `check` field is the name `decide` uses later to find a result, so it does not need to know the position.
- [`OrderBase`](../src/l3_1_parallel_branches/checks.py#L22-L32) holds every key except `results`. It exists so that two state schemas can share these keys, and so that the branch nodes have a type hint that does not mention `results` (see below).
- [`OrderState`](../src/l3_1_parallel_branches/checks.py#L35-L42) is the real state schema. Line 42 is the line that makes this lesson work. In super-step 1, `check_stock` and `check_payment` both write `results`. The `operator.add` reducer tells LangGraph to concatenate the two one-element lists, so neither write is lost. `country` is also written in step 1 (by `normalize_address`), but only by one node, so it needs no reducer.
- [`NoReducerOrderState`](../src/l3_1_parallel_branches/checks.py#L49-L52) is the same state with a plain `list[CheckResult]` on line 52. A key without a reducer becomes a `LastValue` channel, and that channel accepts only one write per super-step. It is used only by the third demo section and by [`test_no_reducer_raises`](../tests/test_parallel_branches.py#L105-L109).

### The check nodes

- The comment on [lines 59–62](../src/l3_1_parallel_branches/checks.py#L59-L62) explains why the branch nodes are hinted `OrderBase` and not `OrderState`. As in lesson 2.3, `add_node` reads the first parameter's hint as the node's input schema and registers its keys as channels. An `OrderState` hint would try to register `results` with `operator.add` in a graph whose `results` has no reducer, and `add_node` would raise a `ValueError` about the channel clash. That error would come before the `InvalidUpdateError` the lesson wants to show. The nodes never read `results`, so `OrderBase` is also the honest hint.
- [`check_stock`](../src/l3_1_parallel_branches/checks.py#L63-L72) lists the lines whose quantity is higher than the stock. Line 70 uses `or`, so an empty list gives "all in stock". Line 72 returns `results` as a one-element list, because `operator.add` adds lists. Returning a bare dict would make the reducer fail with a `TypeError`.
- [`check_payment`](../src/l3_1_parallel_branches/checks.py#L75-L80) compares `balance` with `total`. Like every node here, it returns only the key it changes. LangGraph merges that into the state, so the node does not have to copy the order keys back.

### The address branch

- [`normalize_address`](../src/l3_1_parallel_branches/checks.py#L87-L89) writes only `country`, the last comma-separated part of the address in upper case ("de" becomes "DE").
- [`check_address`](../src/l3_1_parallel_branches/checks.py#L92-L97) reads that `country` on line 94. It can, because it runs one super-step later, after the write from `normalize_address` has been applied. This branch is two nodes long, while the other two branches have one node each. That is why the join on line 142 matters (see below).

### The join node

- [`decide`](../src/l3_1_parallel_branches/checks.py#L104-L116) builds a dict keyed by check name on line 110, then goes through the names in sorted order on line 113. So the problems always come out as address, payment, stock, whatever order `results` is in. [`test_decide_is_order_independent`](../tests/test_parallel_branches.py#L63-L75) checks this by passing the results in two orders.
- This matters because the order of `results` comes from LangGraph, not from your code. In 1.2.16, `apply_writes` (in `langgraph/pregel/_algo.py`, line 255) sorts the tasks of one super-step by task path before it applies their writes. For nodes started by edges, that is the node name. So `check_payment` lands before `check_stock` in step 1, and `check_address` follows in step 2. This is what the version does, not a promise. If you rename a node, the order changes. See the [notes](notes.md) for more.
- `decide` returns `decision` and `problems` and nothing else. Its hint is `OrderState`, but `build_graph` overrides it (line 132).

### The wiring

[`build_graph`](../src/l3_1_parallel_branches/checks.py#L123-L144) takes the state schema as a parameter, so the same nodes and edges can be built with `OrderState` or `NoReducerOrderState`.

- Line 132 passes `input_schema=schema` to `add_node`. An explicit `input_schema` wins over the hint, so `decide` reads the graph's own schema. In the `NoReducerOrderState` graph, this avoids the same channel clash described above.
- Lines 135–137 are the fan-out. Three edges leave `START`, so after the input is written, all three target nodes are triggered in the same super-step and run in parallel. Nothing special is needed for this: several edges from one node are enough.
- Line 139 makes the address branch longer: `check_address` runs in step 2.
- Line 142 is the join. When `add_edge` gets a list of sources, the compiled graph creates one barrier channel for it (named `join:check_stock+check_payment+check_address:decide`). Each listed node marks itself as done in that channel when it finishes. `decide` is triggered only when all three have marked themselves. For Ada, that happens at the end of step 2, so `decide` runs in step 3, exactly once.
  - With three separate `add_edge(..., "decide")` calls instead, each edge fires as soon as its own source finishes. `decide` would then run in step 2 (after `check_stock` and `check_payment`) and again in step 3 (after `check_address`). [`test_waiting_edge_joins_once`](../tests/test_parallel_branches.py#L83-L102) builds this version and counts two `decide` updates.
  - If one of the listed nodes never runs, the barrier never fills. `decide` never runs and LangGraph raises no error. The result simply has no `decision`.
- Line 143 is a plain edge to `END`. Lesson 3.3 replaces the routing after `decide`.

## [\_\_main\_\_.py](../src/l3_1_parallel_branches/__main__.py)

The entry point. [`ADA`, `BOB` and `CLEO`](../src/l3_1_parallel_branches/__main__.py#L7-L27) are three orders. They contain only the input keys: `country`, `results`, `decision` and `problems` are filled in by the nodes. Ada passes all three checks, Bob fails all three, and Cleo fails only the address. [`main`](../src/l3_1_parallel_branches/__main__.py#L30-L68) builds the graph once (line 32) and runs three sections.

- **State after each super-step** ([lines 35–44](../src/l3_1_parallel_branches/__main__.py#L35-L44)): `stream_mode="values"` yields the full state after each super-step, and the first chunk is the input. Line 40 uses `chunk.get("results", [])` because a key that no node has written yet is missing from the state, not set to `None`. The output shows the three steps: payment and stock (and `country`) after step 1, address added after step 2, the decision after step 3.
- **Decisions** ([lines 48–58](../src/l3_1_parallel_branches/__main__.py#L48-L58)): `invoke` returns the final state. Line 53 prints `results` in the order they were stored (payment, stock, address). The problems below are printed in the order `decide` sorted them (address, payment, stock). Seeing the two orders next to each other shows that `decide` does not depend on the stored order.
- **No reducer** ([lines 62–68](../src/l3_1_parallel_branches/__main__.py#L62-L68)): the same nodes and wiring, with `NoReducerOrderState`. In step 1, `check_stock` and `check_payment` both write `results`, and the `LastValue` channel raises `InvalidUpdateError` when it receives two values (in `langgraph/channels/last_value.py`: the message is built on line 61 and raised on line 64). The run stops there, before step 2. Line 68 prints only the first line of the message. The second line is a link to the `INVALID_CONCURRENT_GRAPH_UPDATE` troubleshooting page.

## [test_parallel_branches.py](../tests/test_parallel_branches.py)

- [`test_ada_is_approved`](../tests/test_parallel_branches.py#L19-L26) sorts the check names before comparing them, so it does not depend on the stored order.
- [`test_write_order_on_1_2_16`](../tests/test_parallel_branches.py#L44-L60) is the opposite: it pins the order 1.2.16 produces. Its docstring says this is an implementation detail. If a future LangGraph version fails this test but passes the others, only the order has changed, not the lesson's logic.
- [`test_waiting_edge_joins_once`](../tests/test_parallel_branches.py#L83-L102) builds the separate-edges graph inline. There, `decide` is added without `input_schema`, which is fine because that graph uses `OrderState`.

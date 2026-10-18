# 3.3 Command: Update State and Route in One Step — code walkthrough

The order goes through 3.2's map-reduce and checks as before, and then `decide` does two things with one return value. It writes the decision, and it sends the order to one of three new nodes, `approve`, `hold` or `cancel`. That node writes a notice for the customer. The program shows Ada's order step by step, together with the `Command` that `decide` returns. It prints the decisions and notices for Bob, Cleo and Dora, then the edges the graph drawing shows for `decide`, and repeats 3.2's last two demos. Run it with `./run.sh 3.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 3.2

This lesson extends 3.2's "order-checks" example. Everything before `decide` is unchanged: the `Send` map-reduce, the three checks, the address branch and the list-form join. For those parts, see the [3.2 read-along](../../3.2-map-reduce-send/docs/readalong.md) and the [3.1 read-along](../../3.1-parallel-branches/docs/readalong.md). [pricing.py](../src/l3_3_command/pricing.py) is the same file, only the package name changed.

- [`OrderBase`](../src/l3_3_command/checks.py#L25-L41) has a new key, `notice` (line 41), and `decision` can now also be `"cancelled"` (line 39).
- [`decide`](../src/l3_3_command/checks.py#L144-L165) returns a `Command` instead of a dict. Its return annotation lists the three possible next nodes.
- New region [`route_nodes`](../src/l3_3_command/checks.py#L171-L191) with `approve`, `hold` and `cancel`.
- [`build_graph`](../src/l3_3_command/checks.py#L195-L238) adds the three nodes, each with an edge to `END`, and no longer has an edge out of `decide`.
- [\_\_main\_\_.py](../src/l3_3_command/__main__.py): the step lines show `notice`, the first section prints the `Command`, the decisions loop includes Dora, and there is a new section "Where decide can go".
- The tests moved to [test_command.py](../tests/test_command.py). The 3.2 tests are adapted, and there are new tests for `Command`.

## [checks.py](../src/l3_3_command/checks.py)

The graph: the 3.2 pipeline, with routing added after `decide`.

- Line 4 imports `Literal` for the return annotation of `decide`. Line 8 imports `Command` from `langgraph.types`, where `Send` also lives.

### The state

- [`notice`](../src/l3_3_command/checks.py#L41) is in `OrderBase`, not only in `OrderState`, so the `NoReducerOrderState` graph has it too. `OrderBase` holds every order key except `results` (the one key whose reducer the no-reducer demo removes), so a new order key belongs there. The no-reducer graph fails in super-step 3, before any route node runs, so `notice` plays no part in that error. Only one route node runs per order, so `notice` gets one write and needs no reducer.

### `decide`

- The [comment above `decide`](../src/l3_3_command/checks.py#L140-L143) and the annotation on line 144 are the heart of the lesson. When `add_node` registers a function, it reads the function's type hints. For the return hint it checks for `Command[Literal[...]]` (or a union containing one) and stores the literal values as the node's `ends`, its possible destinations. It does nothing else with the return hint. Nothing checks at run time that `goto` is one of these names.
- Line 155 collects the names of the failed checks in sorted order, and line 156 turns them into the same `problems` strings as in 3.2. Sorting by name keeps the result independent of the order in which the parallel checks wrote `results`.
- The rules on lines 159–165 are checked in order. A failed address wins over everything else, so Bob, who fails all three checks, is cancelled, not put on hold. Cleo fails only the address and is cancelled too. Any other failure means hold (Dora: the MUG is out of stock). No failure means approve.
- Line 159 tests `"address" in failed` and does not look up `by_check["address"]`. A check that has not reported yet is simply missing from the list. This matters in `test_waiting_edge_joins_once`, where `decide` runs once before `check_address` has finished. A direct lookup would raise `KeyError` there.
- Each `Command` on lines 161, 164 and 165 carries two parts. LangGraph applies `update` to the state like a plain node's dict, with the same reducers. It turns `goto` into a write to the hidden channel `branch:to:<node>`, and that channel triggers the named node in the next super-step. A plain edge works through the same kind of channel, so to the runtime a `goto` is one more edge that fires. If `goto` names a node that does not exist, the write goes to an unknown channel: LangGraph logs a warning and the run ends after `decide` with no notice and no exception (see the [notes](notes.md)).

### The route nodes

- [`approve`](../src/l3_3_command/checks.py#L175-L178), [`hold`](../src/l3_3_command/checks.py#L181-L183) and [`cancel`](../src/l3_3_command/checks.py#L186-L188) are ordinary nodes. They return a dict and know nothing about `Command`. They are hinted with `OrderBase` for the same reason as the check nodes in 3.1: a node's hint is registered as its input schema, and `OrderState` would clash in the no-reducer graph.
- `hold` reads `problems` (line 183) and `cancel` reads `country` (line 188). Both keys were written in earlier super-steps: `problems` by `decide` one step before, and `country` by `normalize_address` in step 3. A route node therefore sees everything `decide` saw, plus the `Command.update`.

### The wiring

[`build_graph`](../src/l3_3_command/checks.py#L195-L238) is 3.2's graph with three nodes added at the end.

- Line 211 still passes `input_schema=schema` to `decide`. That only replaces the *input* hint. As the comment on line 210 says, `add_node` still reads the return annotation from the function, so the `ends` are there in both schemas.
- Lines 212–214 register the route nodes.
- Lines 232–234 sit where 3.2 had `add_edge("decide", END)`. There is no edge out of `decide` any more. When `compile()` validates the graph, it treats the `ends` of `decide` like edge targets, as if `decide` had edges to `approve`, `hold` and `cancel`. A name in the `Literal` that is not a node makes `compile()` fail with `Found edge ending at unknown node`. `get_graph()` draws the `ends` as dotted (conditional) edges.
- Lines 235–237 are three separate plain edges to `END`. Only the node that `goto` chose runs, so only one of these edges fires.
- Don't add a static edge out of `decide` next to the `Command`. The edge and the `goto` would both fire in the same super-step. `add_edge("decide", "approve")` would run `cancel` and `approve` together for Bob, and both would write `notice`, which raises `InvalidUpdateError`. A `Command` route adds to a node's edges and never replaces them.
- `add_node` also has a `destinations=` argument that sets the same `ends` without an annotation. This lesson uses the annotation, so the routes sit next to the code that chooses them.

## [\_\_main\_\_.py](../src/l3_3_command/__main__.py)

The entry point. The [orders](../src/l3_3_command/__main__.py#L10-L33) are the same as in 3.2. Line 7 also imports `decide`, so the first section can call it directly. [`main`](../src/l3_3_command/__main__.py#L36-L117) now runs five sections.

- **State after each super-step** ([lines 40–65](../src/l3_3_command/__main__.py#L40-L65)): there are now six steps. Line 55 adds `notice` to each step line. In the output, step 5 (`decide`) already has `decision=approved` but `notice=-`, and the notice appears only in step 6, when `approve` runs. That is the `goto` taking effect one super-step later. Lines 63–64 call `decide` on the final state, outside the graph, and print the `Command` it returns, as lines 43–45 do for the `Send` objects of `route_lines`. `Command` is a dataclass, so its `repr` shows `update` and `goto`.
- **Decisions** ([lines 67–84](../src/l3_3_command/__main__.py#L67-L84)): line 70 adds Dora, so each of the three routes appears once: Bob and Cleo go to `cancel`, Dora goes to `hold`. Line 83 prints the notice. It always exists in the final state because one route node always runs.
- **Where decide can go** ([lines 86–94](../src/l3_3_command/__main__.py#L86-L94)): line 91 draws the compiled graph as Mermaid text, and line 92 keeps the lines that start with `decide -`. The output shows three dotted edges, `decide -.-> approve;` and so on, although `build_graph` has no edge out of `decide`. They come from the `ends`. Without the annotation, this section prints `decide --> __end__;` instead: the drawer adds a solid edge to `END` for any node with no known way out, and the picture is then wrong, although the run is the same.
- **No reducer** ([lines 96–104](../src/l3_3_command/__main__.py#L96-L104)) and **max_concurrency** ([lines 106–117](../src/l3_3_command/__main__.py#L106-L117)) are unchanged from 3.2.

## [test_command.py](../tests/test_command.py)

- [`_checked_state`](../tests/test_command.py#L36-L45) builds the state `decide` sees by calling the check nodes as plain functions. Several tests use it to call `decide` without a graph.
- [`test_decide_returns_a_command_for_each_outcome`](../tests/test_command.py#L68-L83) checks one order per route. It compares `.goto` and `.update` on the returned object, so `decide` can be tested like any function.
- [`test_route_nodes_write_only_the_notice`](../tests/test_command.py#L86-L92) gives `hold` and `cancel` the keys that earlier steps would have written (`problems`, `country`).
- [`test_end_to_end_decisions_and_notices`](../tests/test_command.py#L95-L120) checks the notice, not only the decision. A misspelled `goto` would still set the decision, but no route node would run and there would be no notice.
- [`test_only_the_chosen_node_runs`](../tests/test_command.py#L123-L141) uses `stream_mode="updates"` to list which nodes ran. Line 141 shows that the update chunk of `decide` contains only `Command.update`. The `goto` is not part of the state and never shows up in the stream.
- [`test_annotation_declares_the_routes`](../tests/test_command.py#L144-L154) looks inside the builder. `decide` has no edge (line 147) and no conditional branch (line 148), and its `ends` hold the three names from the `Literal` (line 149). The drawing has exactly three conditional edges from `decide`.
- [`test_without_annotation_only_the_drawing_changes`](../tests/test_command.py#L157-L175) replaces `checks.decide` with a wrapper that has no return hint, then builds the graph. This works because `build_graph` looks up the name `decide` in the `checks` module. Bob is still cancelled, but the drawing has only the solid `decide -> __end__` edge.
- [`test_super_steps_on_1_2_16`](../tests/test_command.py#L178-L202) now expects seven chunks (input plus six steps). Lines 195–197 pin that the decision lands in step 5 and the notice in step 6.
- [`test_decide_is_order_independent`](../tests/test_command.py#L247-L254) compares two `Command` objects with `==`, which works because `Command` is a dataclass.
- [`test_waiting_edge_joins_once`](../tests/test_command.py#L262-L291) builds the three-separate-edges graph inline. It now adds the route nodes (lines 274–276 and 288–290) where 3.2 had `decide -> END`. Here `decide` runs twice, and the first run, before `check_address`, relies on the `"address" in failed` test in `decide`.
- The other tests ([`route_lines`, `price_line`](../tests/test_command.py#L53-L65), [`sum_total`](../tests/test_command.py#L205-L212), [`max_concurrency`](../tests/test_command.py#L215-L244), [no reducer](../tests/test_command.py#L294-L298)) are 3.2's, unchanged apart from the package name.

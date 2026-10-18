# 7.1 Stream Modes: values, updates and Typed v2 Parts — code walkthrough

The program sends one order through a three-node graph (pick, pack, ship) and streams the same run four times: with `stream_mode="values"`, with `stream_mode="updates"`, with a list of both modes, and with `version="v2"`, where every chunk is a typed dict. Run it with `./run.sh 7.1` from the course root.
The concept itself is explained in the [notes](notes.md).

## Where the code comes from

This is the first lesson of module 7, and its example ("order-tracker") is new. Lessons 7.2 to 7.4 extend it. That is why the graph lives in its own module with a `build_graph()` that takes no parameters, why `items` is a list of SKUs, and why the part renderer sits in a separate file with a fallback `case`: later lessons add one `case` each.

[pyproject.toml](../pyproject.toml#L6) depends only on `langgraph==1.2.16`. Nothing else is imported directly; there is no model, no checkpointer and no service, so the run is offline and always prints the same lines.

## [orders.py](../src/l7_1_stream_modes/orders.py)

The state, the three nodes and the graph. This is what gets streamed; the file knows nothing about streaming.

- [`OrderState`](../src/l7_1_stream_modes/orders.py#L14-L25) has no reducers, so each key a node returns replaces the old value. `status`, `box` and `tracking` on [lines 23-25](../src/l7_1_stream_modes/orders.py#L23-L25) are `NotRequired` because the input has only `order_id` and `items`. LangGraph does not fill in missing keys, so the first `values` chunk really has just two keys.
- [`pick`](../src/l7_1_stream_modes/orders.py#L36-L38), [`pack`](../src/l7_1_stream_modes/orders.py#L41-L43) and [`ship`](../src/l7_1_stream_modes/orders.py#L46-L48) each return a small dict with only the keys they set. After a node finishes, LangGraph writes that dict into the state channels. The `"updates"` mode reports the dict exactly as the node returned it; the `"values"` mode reads all channels after the step and reports the merged result. If the nodes returned the whole state, the two modes would look almost the same.
- The box rule on [line 43](../src/l7_1_stream_modes/orders.py#L43) reads `state["items"]`: the node gets the full current state, even though it returns only part of it. Two items give `"small"`; the second test uses three items to get `"large"`.
- [`build_graph`](../src/l7_1_stream_modes/orders.py#L55-L66) wires a straight line, [lines 62-65](../src/l7_1_stream_modes/orders.py#L62-L65). With one node per super-step, every step produces exactly one `updates` chunk and one `values` chunk, which keeps the output easy to compare across the four sections.
- `builder.compile()` matters for streaming: `StateGraph.compile()` sets the compiled graph's default `stream_mode` to `"updates"` (a plain `Pregel` defaults to `"values"`). The return annotation itself has no effect at run time. So `graph.stream(ORDER)` without a mode is the same as section (b).

## [render.py](../src/l7_1_stream_modes/render.py)

One function that turns a v2 part into a line of text. It is only used by section (d) of `__main__.py`.

- [`describe`](../src/l7_1_stream_modes/render.py#L7-L38) takes a `StreamPart`, imported on [line 3](../src/l7_1_stream_modes/render.py#L3). `StreamPart` is only a type: at run time each part is a plain `dict`. The union of TypedDicts exists so that a type checker knows what `data` holds once `type` is known.
- The `match part["type"]` on [line 19](../src/l7_1_stream_modes/render.py#L19) is that check. Inside `case "values"` a type checker treats `part` as `ValuesStreamPart`, so `part["interrupts"]` is allowed; inside `case "updates"` it is `UpdatesStreamPart`, which has no `interrupts` key at all.
- The `values` case, [lines 23-26](../src/l7_1_stream_modes/render.py#L23-L26), prints `status` with `.get('status', '-')`, because the first values part is the input and has no `status` yet. That is the `status=-` in the output. `interrupts` is always the empty tuple here, so it prints `interrupts=0`; it would hold `Interrupt` objects only if the run paused (lesson 6.1).
- The `updates` case, [lines 31-34](../src/l7_1_stream_modes/render.py#L31-L34), loops over `part["data"].items()`, because `data` is the same `{node_name: returned_dict}` mapping that v1 `"updates"` yields. In this linear graph each part has one node, so the join produces one line per part.
- `ns` is printed in both cases and is always `()`: the run streams only the top-level graph. It becomes a non-empty path only for subgraphs streamed with `subgraphs=True`.
- The fallback `case other` on [lines 35-38](../src/l7_1_stream_modes/render.py#L35-L38) catches every other type and binds the type string to `other`. No such part is produced in this lesson; the last test calls it with a hand-made `"custom"` part.

## [\_\_main\_\_.py](../src/l7_1_stream_modes/__main__.py)

The live run. [`ORDER`](../src/l7_1_stream_modes/__main__.py#L12) is the input, and [`main`](../src/l7_1_stream_modes/__main__.py#L15-L63) builds the graph once and streams it four times. Each `graph.stream(...)` call is a fresh run of the same graph: there is no checkpointer, so nothing carries over between sections.

### values ([lines 19-27](../src/l7_1_stream_modes/__main__.py#L19-L27))

The loop on [line 24](../src/l7_1_stream_modes/__main__.py#L24) gets the whole state dict on every iteration. There are four chunks for three nodes: the first is the input, emitted before `pick` runs, and then one after each step. Each chunk repeats everything the previous one had, which is why the lines get longer.

### updates ([lines 29-38](../src/l7_1_stream_modes/__main__.py#L29-L38))

The loop on [line 35](../src/l7_1_stream_modes/__main__.py#L35) gets one dict per node that ran, keyed by the node name given in `add_node`. There is no chunk for the input, so there are three lines. The values in these dicts are exactly what `pick`, `pack` and `ship` returned: `ship`'s chunk has no `box`, because `ship` did not return one.

### A list of modes in v1 ([lines 40-49](../src/l7_1_stream_modes/__main__.py#L40-L49))

- Passing a list on [line 46](../src/l7_1_stream_modes/__main__.py#L46) changes what each item is: a `(mode, chunk)` tuple instead of a bare chunk. That is why this loop unpacks two names while the loops above take one. The tuple shape comes from the list, not from the number of modes: a one-element list also gives tuples, and a plain string gives bare chunks.
- Both modes come from the same single run, so the output interleaves them: the input values, then for each step its updates chunk followed by the values chunk after it. The third test checks that `["updates", "values"]` gives the same list, so the order you write the modes in does not matter.
- `{mode:<7}` on [line 47](../src/l7_1_stream_modes/__main__.py#L47) pads `values` to the width of `updates` so the chunks line up.

### v2 parts ([lines 51-64](../src/l7_1_stream_modes/__main__.py#L51-L64))

- `version="v2"` on [line 59](../src/l7_1_stream_modes/__main__.py#L59) does not change how the graph runs, only the shape of what `stream` yields. Every item is a dict with `type`, `ns` and `data`, whether you ask for one mode or several. It is the streaming counterpart of `invoke(..., version="v2")` returning a `GraphOutput` in lesson 6.1 ([its code](../../../6-human-in-the-loop/6.1-interrupt-and-resume/src/l6_1_interrupt_and_resume/__main__.py#L90), [its notes](../../../6-human-in-the-loop/6.1-interrupt-and-resume/docs/notes.md#the-v2-format)).
- [Lines 60-61](../src/l7_1_stream_modes/__main__.py#L60-L61) print the keys of the first two parts. `parts[0]` is the values part of the input and `parts[1]` the updates part of `pick`, the same order as in the v1 section. The output shows the one difference in shape: only the values part has `interrupts`.
- The loop on [lines 62-63](../src/l7_1_stream_modes/__main__.py#L62-L63) hands each part to `describe`, which decides what to print from `part["type"]`. Because the shape does not depend on the mode list, the same loop would work unchanged with `stream_mode="updates"` alone.

## [test_stream_modes.py](../tests/test_stream_modes.py)

The tests check the chunks themselves instead of the printed text. They import `ORDER` from `__main__` ([line 5](../tests/test_stream_modes.py#L5)) so the tests and the live run use the same input.

- [`test_values_streams_input_then_full_state`](../tests/test_stream_modes.py#L23-L30) compares the first chunk with `dict(ORDER)` and checks the `status` sequence `[None, "picked", "packed", "shipped"]`: input first, then one full state per node.
- [`test_updates_streams_only_node_returns`](../tests/test_stream_modes.py#L33-L41) compares `"updates"` with the exact node returns, then shows on [line 37](../tests/test_stream_modes.py#L37) that `graph.stream(ORDER)` with no mode gives the same list. [Lines 39-41](../tests/test_stream_modes.py#L39-L41) cover the `"large"` box branch.
- [`test_list_of_modes_yields_tuples`](../tests/test_stream_modes.py#L44-L58) checks that every item is a 2-tuple, the mode sequence, and on [line 58](../tests/test_stream_modes.py#L58) that reversing the list gives an equal result.
- [`_v2_parts`](../tests/test_stream_modes.py#L61-L65) turns every warning into an error while streaming, so the test fails if `version="v2"` ever emits a deprecation warning.
- [`test_v2_parts_have_fixed_shape`](../tests/test_stream_modes.py#L68-L88) checks that the parts are plain dicts with the expected keys, and on [lines 82-85](../tests/test_stream_modes.py#L82-L85) that their `data` equals the v1 chunks of each mode. So for this state (a TypedDict, no interrupts) v2 adds a wrapper and the payload is the same. [Lines 87-88](../tests/test_stream_modes.py#L87-L88) show that a single mode in v2 also yields dicts.
- [`test_describe_renders_each_part_type`](../tests/test_stream_modes.py#L91-L105) checks the seven lines of section (d) and, on [lines 103-105](../tests/test_stream_modes.py#L103-L105), the fallback case with a hand-made `"custom"` part.

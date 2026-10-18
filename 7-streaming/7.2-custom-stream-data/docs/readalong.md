# 7.2 Custom Progress Events with get_stream_writer — code walkthrough

The program runs the same order through the pick, pack and ship graph from 7.1. This time `pack` and `ship` send their own progress data into the stream, and the program reads that data four ways: with `stream_mode="custom"` alone, mixed with `"updates"` in `version="v2"`, with `"updates"` only (the progress is dropped), and by calling the nodes directly, outside a run. Run it with `./run.sh 7.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 7.1

The graph, the state and the input are the same as in 7.1. For the parts that did not change (`OrderState`, `pick`, `build_graph`, the `values` and `updates` cases of `describe`), see the [7.1 walkthrough](../../7.1-stream-modes/docs/readalong.md).

- [orders.py](../src/l7_2_custom_stream_data/orders.py#L9-L12) imports `get_stream_writer` from `langgraph.config` and `Runtime` from `langgraph.runtime`.
- [`pack`](../src/l7_2_custom_stream_data/orders.py#L43-L57) gets the writer with `get_stream_writer()` and writes one progress dict per item. It returns the same update as in 7.1.
- [`ship`](../src/l7_2_custom_stream_data/orders.py#L60-L69) takes a new `runtime: Runtime` parameter and writes the tracking label through `runtime.stream_writer`. It returns the same update as in 7.1.
- [`describe`](../src/l7_2_custom_stream_data/render.py#L35-L37) has a new `case "custom"` above the fallback. The fallback comment now says that lesson 7.3 adds `"messages"`.
- [\_\_main\_\_.py](../src/l7_2_custom_stream_data/__main__.py#L17-L71) replaces the four sections from 7.1 with four new ones.
- [test_custom_stream_data.py](../tests/test_custom_stream_data.py) replaces `test_stream_modes.py`.
- [pyproject.toml](../pyproject.toml#L6) still depends only on `langgraph==1.2.16`. There is still no model, no checkpointer and no service.

## [orders.py](../src/l7_2_custom_stream_data/orders.py)

The state, the nodes and the graph. Two of the nodes now write to the stream, and each one gets the writer in a different way.

- [`pack`](../src/l7_2_custom_stream_data/orders.py#L43-L57) uses the first way. `get_stream_writer()` on [line 48](../src/l7_2_custom_stream_data/orders.py#L48) takes no arguments. It reads the config of the run that is executing the node and returns the `stream_writer` of that run's `Runtime`. That is why it only works while a run is executing the node. If you call it at import time or in a plain function call, there is no run config and it raises `RuntimeError` (section d).
- What the writer does depends on how the caller started the run. `stream()` builds a new writer for every run. If `"custom"` is among the requested modes, the writer puts each value on the stream as a `custom` chunk. Otherwise it is a function that does nothing. `pack` cannot tell which one it got, and it does not need to.
- The call `writer({...})` on [line 56](../src/l7_2_custom_stream_data/orders.py#L56) runs once per item inside the loop on [line 50](../src/l7_2_custom_stream_data/orders.py#L50), so two items give two progress chunks. Each payload carries `"node"` because a custom chunk does not say which node wrote it (section a). The dict is built fresh on every call, because the writer passes the object on without copying it (experiment 2 in the notes shows what goes wrong otherwise).
- [Line 57](../src/l7_2_custom_stream_data/orders.py#L57) is the node's return value. Only this dict becomes an `updates` chunk and goes into the state. The progress dicts do not go into the state, so `invoke()` returns the same final state as in 7.1. The box rule now reuses `total` instead of calling `len()` again.
- [`ship`](../src/l7_2_custom_stream_data/orders.py#L60-L69) uses the second way. LangGraph sees the parameter named `runtime` and passes in the run's `Runtime` object, the same mechanism as `runtime.context` in [lesson 2.4](../../../2-state/2.4-runtime-context/docs/readalong.md). [Line 68](../src/l7_2_custom_stream_data/orders.py#L68) calls `runtime.stream_writer`, which is the same writer `get_stream_writer()` would have returned. The difference shows up outside a run: `ship` gets its writer as an argument, so you can call it with any `Runtime` you build yourself.
- [`build_graph`](../src/l7_2_custom_stream_data/orders.py#L76-L87) is unchanged. `add_node("ship", ship)` needs nothing extra for the new parameter, because LangGraph finds `runtime` in the signature on its own.

## [render.py](../src/l7_2_custom_stream_data/render.py)

`describe` turns one v2 part into a line of text. It has one new case.

- The `case "custom"` on [lines 35-37](../src/l7_2_custom_stream_data/render.py#L35-L37) prints `part["data"]` as it is. For a custom part, `data` is exactly the object the node passed to the writer. LangGraph does not wrap it, add the node name or convert it. `ns` is `()`, because all writes come from the top-level graph.
- The two spaces after `[custom]` make it line up with `[updates] ` and `[values]  ` in the output.
- The fallback `case other` on [lines 38-41](../src/l7_2_custom_stream_data/render.py#L38-L41) stays and still catches every other part type. In 7.1 the last test passed a hand-made `"custom"` part to the fallback. Now that `"custom"` has its own case, the test passes a `"tasks"` part instead.

## [\_\_main\_\_.py](../src/l7_2_custom_stream_data/__main__.py)

The live run. [`ORDER`](../src/l7_2_custom_stream_data/__main__.py#L14) is the same input as in 7.1. [`main`](../src/l7_2_custom_stream_data/__main__.py#L17-L71) builds the graph once and runs it three times in sections (a) to (c). Section (d) does not use the graph at all. [Line 10](../src/l7_2_custom_stream_data/__main__.py#L10) also imports `pack` and `ship` so that section (d) can call them directly.

### Custom alone ([lines 21-29](../src/l7_2_custom_stream_data/__main__.py#L21-L29))

- With the single mode `"custom"` in v1 on [line 26](../src/l7_2_custom_stream_data/__main__.py#L26), each item is the bare value from a `writer(...)` call: three dicts, two from `pack` and one from `ship`. `pick` writes nothing, so it does not appear at all. The state and the node returns do not appear either.
- The graph still runs completely. The updates are made, but this caller did not ask for them.

### Custom next to updates in v2 ([lines 31-42](../src/l7_2_custom_stream_data/__main__.py#L31-L42))

- The call on [line 39](../src/l7_2_custom_stream_data/__main__.py#L39) asks for both modes with `version="v2"`, so every item is a dict with `type`, `ns` and `data`, and `describe` picks the line format from `type`. A custom part has exactly these three keys, and no `interrupts` key.
- The output shows the order: the two `pack` progress lines come before `pack`'s updates line. The writer sends while the node runs, and the update exists only after the node returns. The same goes for `ship`: its label comes before its update. This is the order that this run and the tests check. No claim is made here about graphs with parallel nodes.
- Asking for `"custom"` also turns on eager streaming in `stream()`, so each chunk reaches the caller as soon as the node writes it, not at the end of the step. With fast nodes you can't see the difference. Experiment 1 in the notes slows `pack` down to show it.

### Updates only ([lines 44-54](../src/l7_2_custom_stream_data/__main__.py#L44-L54))

- The loop on [line 50](../src/l7_2_custom_stream_data/__main__.py#L50) runs the same nodes, with the same writer calls, but `"custom"` is not requested. So the run gives the nodes the do-nothing writer. The three chunks are exactly 7.1's updates, and there is no error and no warning.
- `invoke()` on [line 52](../src/l7_2_custom_stream_data/__main__.py#L52) behaves the same way: its default mode is `"values"`, so the progress is dropped and the run finishes with `status=shipped`. A node that writes progress therefore works unchanged for callers that never stream.

### Outside a run ([lines 56-71](../src/l7_2_custom_stream_data/__main__.py#L56-L71))

- [Lines 60-63](../src/l7_2_custom_stream_data/__main__.py#L60-L63) call `pack(ORDER)` as a plain function. `get_stream_writer()` looks for the run config, finds none and raises `RuntimeError`. The message names `get_config`, because that is the function `get_stream_writer()` uses to read the config.
- [Line 68](../src/l7_2_custom_stream_data/__main__.py#L68) calls `ship` with a hand-made `Runtime(stream_writer=written.append)`. To `ship`, `list.append` is a writer like any other: it is a callable that takes one value. So the payload ends up in `written` ([line 67](../src/l7_2_custom_stream_data/__main__.py#L67)), and [lines 69-70](../src/l7_2_custom_stream_data/__main__.py#L69-L70) print both the return value and what was written. This is how you test a node's progress output without building a graph.

## [test_custom_stream_data.py](../tests/test_custom_stream_data.py)

The tests check the chunks themselves and import `ORDER` from `__main__`, so they use the same input as the live run. [`PAYLOADS`](../tests/test_custom_stream_data.py#L11-L15) holds the three expected writer values, and several tests compare against it.

- [`test_custom_alone_yields_only_writer_payloads`](../tests/test_custom_stream_data.py#L18-L27) checks section (a). It then runs a three-item order and checks `done` 1, 2, 3 with `total` 3, so the progress really follows `state["items"]`.
- [`_v2_parts`](../tests/test_custom_stream_data.py#L30-L34) turns every warning into an error while streaming, as in 7.1.
- [`test_custom_and_updates_interleave_in_v2`](../tests/test_custom_stream_data.py#L37-L54) checks the exact `type` sequence of section (b), the three keys and `ns == ()` of every custom part, and that their `data` equals `PAYLOADS`. [Line 54](../tests/test_custom_stream_data.py#L54) checks that `["custom", "updates"]` gives an equal list, so the order of the mode list does not matter.
- [`test_without_custom_the_writer_calls_are_dropped`](../tests/test_custom_stream_data.py#L57-L71) checks section (c). It also checks that the final state from `invoke()` has only the five state keys, which shows that the progress never entered the state.
- [`test_nodes_outside_a_run`](../tests/test_custom_stream_data.py#L74-L83) checks section (d). [Line 83](../tests/test_custom_stream_data.py#L83) adds the case the live run only mentions in a comment: a plain `Runtime()` also works, because its default `stream_writer` does nothing.
- [`test_describe_renders_custom_parts_and_keeps_fallback`](../tests/test_custom_stream_data.py#L86-L97) checks the six printed lines of section (b) and, on [line 97](../tests/test_custom_stream_data.py#L97), the fallback with a hand-made `"tasks"` part.

# 7.4 Event Streaming with stream_events v3 — code walkthrough

The program runs the same order through the same pick, pack, ship and confirm graph as in 7.3. Only the caller changes. Each section starts a new run with `graph.stream_events(ORDER, version="v3")` and reads it a different way: state snapshots and the final output, one stream per model call, both of those interleaved, opt-in `updates` and `custom` projections, and the raw protocol events. Run it with `./run.sh 7.4` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 7.3

- [pyproject.toml](../pyproject.toml#L6) has the same two pins as 7.3.
- [orders.py](../src/l7_4_event_streaming/orders.py) is a byte-for-byte copy of 7.3's. The graph does not change. For its walkthrough, see the [7.3 walkthrough](../../7.3-streaming-llm-tokens/docs/readalong.md).
- `render.py` is gone. Its `describe` formatted v2 part dicts. The v3 projections hand out ready-made objects (state dicts, `ChatModelStream` objects), so nothing needs to render them.
- [\_\_main\_\_.py](../src/l7_4_event_streaming/__main__.py#L9-L14) imports `warnings`, `Counter`, `CustomTransformer` and `UpdatesTransformer`, and no longer imports `describe`.
- [`main`](../src/l7_4_event_streaming/__main__.py#L20-L149) starts with a warning filter and replaces 7.3's five `stream_mode="messages"` sections with five `stream_events` sections.
- [test_event_streaming.py](../tests/test_event_streaming.py) replaces `test_streaming_llm_tokens.py`.

## [orders.py](../src/l7_4_event_streaming/orders.py)

Unchanged, but one thing works differently behind it.

- The comment in [`confirm`](../src/l7_4_event_streaming/orders.py#L100-L105) talks about `stream_mode="messages"`. That is still what happens: v3 needs the messages mode for its `messages` projection, so it asks `stream()` for it on your behalf. It also sets a flag in the config (`CONFIG_KEY_STREAM_MESSAGES_V2`) that swaps the handler from 7.3 for `StreamMessagesHandlerV2`. That handler still makes `.invoke()` stream, but it reports each call as a sequence of events (message start, content blocks, message finish) instead of bare chunks. You see those events in the last section.
- The `TAG_NOSTREAM` call on [line 114](../src/l7_4_event_streaming/orders.py#L114) is skipped the same way. The new handler does not register a call with that tag when it starts, so all its later events are dropped.

## [\_\_main\_\_.py](../src/l7_4_event_streaming/__main__.py)

The live run. [`ORDER`](../src/l7_4_event_streaming/__main__.py#L17) is the same input as before. [`main`](../src/l7_4_event_streaming/__main__.py#L20-L149) builds the graph once on [line 38](../src/l7_4_event_streaming/__main__.py#L38) and starts six runs: one per section, and one more with plain `stream()` at the end.

### The beta warning ([lines 22-37](../src/l7_4_event_streaming/__main__.py#L22-L37))

- `stream_events(version="v3")` and the `GraphRunStream` class are both marked `@beta` in langgraph 1.2.16, so every call prints two `LangChainBetaWarning` lines to stderr. The filter on [lines 34-36](../src/l7_4_event_streaming/__main__.py#L34-L36) matches by message prefix and by `DeprecationWarning`, the parent class of `LangChainBetaWarning`. That way it hides only this warning, and it does not need the private `langchain_core._api` module.
- Where the filter sits matters. Python checks warning filters newest first. Importing `langchain_core` adds its own "show beta warnings" filter, so a filter set before that import would lose. Inside `main` it comes after the imports, so it wins (experiment 5).

### run.values and run.output ([lines 40-58](../src/l7_4_event_streaming/__main__.py#L40-L58))

- The call on [line 46](../src/l7_4_event_streaming/__main__.py#L46) does not run anything yet. It returns a `GraphRunStream`, a lazy object. The graph moves forward only while you pull items from it, in this thread.
- Behind the scenes it calls `stream()` with `subgraphs=True`, `version="v2"` and the union of the stream modes its transformers ask for. That is why it refuses your own `stream_mode=` or `subgraphs=` with a `TypeError` (experiment 3).
- The loop on [lines 49-50](../src/l7_4_event_streaming/__main__.py#L49-L50) gets the same full snapshots as `stream_mode="values"`: first the input with 2 keys, then one per node, ending with 8 keys after `confirm`. `.get('status', '-')` is needed because the input has no `status` yet.
- `run.output` on [line 56](../src/l7_4_event_streaming/__main__.py#L56) is a property. If the run is still going, reading it drives the run to the end. Here the loop already did that, so it just returns the last state. The `note` is in it, although its call was never streamed.

### run.messages ([lines 60-79](../src/l7_4_event_streaming/__main__.py#L60-L79))

- Each item of `run.messages` on [line 73](../src/l7_4_event_streaming/__main__.py#L73) is a `ChatModelStream` for a whole model call. You get two items, the email and the SMS. In 7.3 you got twelve token chunks and had to tell the calls apart yourself.
- `message.node` on [line 74](../src/l7_4_event_streaming/__main__.py#L74) is the node that made the call. A `ChatModelStream` has no `tags`, so the email and the SMS can only be told apart by their order here.
- The inner loop on [lines 75-76](../src/l7_4_event_streaming/__main__.py#L75-L76) pulls the text deltas of this one call as they arrive. That is the same "typing" effect as in 7.3, but now each reply ends on its own line instead of running into the next one.

### run.interleave ([lines 81-98](../src/l7_4_event_streaming/__main__.py#L81-L98))

- A projection is a single-consumer cursor. It keeps items only after something has subscribed to it, and only one subscriber is allowed. If you drained `run.values` first and then read `run.messages`, the run would already be over, and the messages would be lost (experiments 1 and 2).
- `run.interleave("values", "messages")` on [line 92](../src/l7_4_event_streaming/__main__.py#L92) subscribes to both before the run starts and yields `(name, item)` pairs in the order they were produced. The two messages come after `ship`'s snapshot and before `confirm`'s, because they are sent while `confirm` is still running.
- `str(item.text)` on [line 96](../src/l7_4_event_streaming/__main__.py#L96) reads the whole reply at once. That pulls the run forward until this call has finished, and only then does the loop go on.

### Opt-in projections ([lines 100-118](../src/l7_4_event_streaming/__main__.py#L100-L118))

- By default a run has four projections: `values`, `messages`, `lifecycle` and `subgraphs`. Each transformer declares the stream modes it needs, and v3 asks the graph only for those. So in the sections above, the graph never even produced the progress events of `pack` and `ship`.
- [Lines 111-113](../src/l7_4_event_streaming/__main__.py#L111-L113) pass `UpdatesTransformer` and `CustomTransformer` as classes, not instances. v3 builds one instance per scope (the root graph and each subgraph) and rejects an instance with a `TypeError`. The classes add `"updates"` and `"custom"` to the requested modes, and `run.updates` and `run.custom` to the run.
- [Line 114](../src/l7_4_event_streaming/__main__.py#L114) prints the keys of `run.extensions`, a read-only mapping from projection name to its channel. Without the two transformers, `run.updates` raises an `AttributeError` that lists the registered projections (experiment 3).
- The loop on [lines 115-116](../src/l7_4_event_streaming/__main__.py#L115-L116) shows the `pack` and `ship` events of 7.2 again, each before the update of its node. The `custom` items are the dicts the writer got, unchanged.

### Raw protocol events ([lines 120-149](../src/l7_4_event_streaming/__main__.py#L120-L149))

- Iterating the run itself on [line 131](../src/l7_4_event_streaming/__main__.py#L131) gives the events that the projections are built from. Each one is a dict with `method` (the channel), `params` (namespace, timestamp, data) and an increasing `seq`.
- For a `messages` event, `params["data"]` is a `(payload, metadata)` pair. [Lines 133-135](../src/l7_4_event_streaming/__main__.py#L133-L135) count them by `payload["event"]`. Each of the two calls gives one message start, one content block start, its deltas (9 plus 3), one content block finish and one message finish. `ChatModelStream` assembles exactly these events for you. The `metadata` part still has `langgraph_node` and `tags`, so tag filtering is possible at this level.
- [Lines 144-147](../src/l7_4_event_streaming/__main__.py#L144-L147) run the same graph through `stream()` with the same two modes. You get 5 values parts and 12 bare token chunks. The difference is the choice. `stream()` is the stable, low-level API: its `values`, `updates` and `custom` parts are plain dicts, but its `messages` parts carry `AIMessageChunk` objects, which `json.dumps` rejects, so you convert them before sending them over a wire protocol such as SSE. v3 is the higher-level object API for code in the same process, and it is still experimental in 1.2.16. The [notes](notes.md) expand on when to use which.

## [test_event_streaming.py](../tests/test_event_streaming.py)

The tests import `ORDER` from `__main__`. [Line 10](../tests/test_event_streaming.py#L10) sets a module-level `pytestmark` that ignores the beta warning, the same filter as in `main`, so the tests pass with `-W error`.

- [`test_stream_events_returns_run_stream_and_warns`](../tests/test_event_streaming.py#L16-L24) catches the beta warning with `pytest.warns`. `pytest.warns` records the warning even with the module-level ignore. The test also checks the type of the run, the four default projections, and the `TypeError` for `stream_mode=`.
- [`test_values_and_output`](../tests/test_event_streaming.py#L27-L43) checks the five statuses, that `run.output` equals the last snapshot and the full 8-key state, and that `run.interrupted` is `False`.
- [`test_messages_one_stream_per_call`](../tests/test_event_streaming.py#L46-L54) checks the two `ChatModelStream` objects and their texts, and `ms[0].output.text`, the assembled `AIMessage`. It does not check `message_id`, which is random on every run.
- [`test_projections_must_be_subscribed_in_time`](../tests/test_event_streaming.py#L57-L71) shows the subscription rule. After `run.values`, `run.messages` is empty, and a second `run.values` raises `RuntimeError` that suggests `.tee(n)`. Then, on a new run, `interleave` gets both projections in arrival order. [Line 71](../tests/test_event_streaming.py#L71) checks what happens after `interleave()`: a second `run.values` does not raise, it just returns `[]`. `interleave()` drops its subscriptions when it finishes, so a new read is allowed but finds nothing left.
- [`test_opt_in_projections`](../tests/test_event_streaming.py#L74-L88) checks the `AttributeError` for `run.updates` on a default run and the three `custom` items with the transformers.

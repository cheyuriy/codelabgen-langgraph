# 10.3 Error Handlers and Node Defaults — code walkthrough

The quote graph from 10.2 no longer crashes when the rate call fails for good. `fetch_rate` gets its own error handler that sends a flat-rate estimate, every other node falls back to a graph-wide default handler, and a new last node, `write_reply`, turns whatever happened into a reply. Five quotes in a row show a healthy run, an outage and a hang that both end in an estimate, an unknown city caught by the default handler, and a too-heavy parcel that still fails the run. Run it with `./run.sh 10.3` from the course root. The whole run takes about 1.5 seconds.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 10.2

- [`service.py`](../src/l10_3_error_handlers/service.py) is unchanged.
- The imports in `graph.py` add [`Literal`](../src/l10_3_error_handlers/graph.py#L9), [`NodeError`](../src/l10_3_error_handlers/graph.py#L12) and [`Command`](../src/l10_3_error_handlers/graph.py#L15).
- [`QuoteState`](../src/l10_3_error_handlers/graph.py#L29-L32) gains the keys `error` and `reply`.
- [`RATE_RETRY`](../src/l10_3_error_handlers/graph.py#L56-L58) and [`RATE_TIMEOUT`](../src/l10_3_error_handlers/graph.py#L77-L78) keep their values. Only a comment is new: they are graph-wide defaults now.
- The `error_handlers` region is new: [`FALLBACK_RATE_PER_KG`](../src/l10_3_error_handlers/graph.py#L115), [`describe_failure`](../src/l10_3_error_handlers/graph.py#L118-L125), [`fallback_quote`](../src/l10_3_error_handlers/graph.py#L130-L153) and [`record_failure`](../src/l10_3_error_handlers/graph.py#L156-L162).
- [`lookup_zone`](../src/l10_3_error_handlers/graph.py#L181) is now `async def`. [`write_reply`](../src/l10_3_error_handlers/graph.py#L195-L204) is a new node.
- In `build_graph`, [`set_node_defaults`](../src/l10_3_error_handlers/graph.py#L215-L219) is new. `fetch_rate` is [added](../src/l10_3_error_handlers/graph.py#L224) with `error_handler=fallback_quote` only, without `retry_policy=` and `timeout=`. The edge `fetch_rate -> END` became [`fetch_rate -> write_reply -> END`](../src/l10_3_error_handlers/graph.py#L229-L230).
- [`__main__.py`](../src/l10_3_error_handlers/__main__.py#L34-L79) has five new sections instead of the four from 10.2, and no longer imports `time`, `NodeTimeoutError` or `RATE_TIMEOUT`.
- [`test_error_handlers.py`](../tests/test_error_handlers.py) is new. In the old test files, three tests that expected an exception now check the handler's result: [`test_retries_stop_at_max_attempts`](../tests/test_graph.py#L21-L27), [`test_permanent_hang_exhausts_retries`](../tests/test_timeouts.py#L34-L41) and [`test_run_timeout_is_a_hard_cap_and_not_retried`](../tests/test_timeouts.py#L44-L52).

## [graph.py](../src/l10_3_error_handlers/graph.py)

The state, the shared policies, the two error handlers, the three nodes and the wiring. `retry_rate`, `zone_cache_key`, `ZONE_CACHE` and `fetch_rate` work as in 10.2.

- [`QuoteState`](../src/l10_3_error_handlers/graph.py#L21-L32): `error` is written only by a handler, `reply` only by `write_reply`. A `TypedDict` state does not fill in missing keys. A key nobody wrote is simply not in the dict a node receives, so `state["error"]` would raise `KeyError` on a healthy run. That is why `write_reply` tests with `in`.
- [`retry_rate`](../src/l10_3_error_handlers/graph.py#L39-L53) has not changed, but it now decides for every node, not only `fetch_rate`. For `lookup_zone`'s `KeyError` it reaches line 53 and returns `False`, so an unknown city is looked up once and goes straight to the handler.
- [`RATE_RETRY`](../src/l10_3_error_handlers/graph.py#L59-L73) and [`RATE_TIMEOUT`](../src/l10_3_error_handlers/graph.py#L81-L90) keep their 10.2 names, although they now cover all nodes. Renaming them would only add noise to the diff.

### The error handlers (lines 112–165)

- [`FALLBACK_RATE_PER_KG`](../src/l10_3_error_handlers/graph.py#L115): 9.0 is above the real rates 4.0 and 7.5 in `service.py`, so the estimate can only overcharge. In section 3 the Paris parcel costs 9.0 instead of 7.5.
- [`describe_failure`](../src/l10_3_error_handlers/graph.py#L118-L125) reads the two fields of `NodeError` that the lesson needs: `error.node`, the name of the node that failed, and `error.error`, the exception it raised last. The result, such as `"KeyError in lookup_zone"`, ends up in both the state and the reply.
- [`fallback_quote`](../src/l10_3_error_handlers/graph.py#L130-L153) is a normal node function with a second parameter. LangGraph sees the `NodeError` annotation and passes the failure in, just as it passes `runtime` to `fetch_rate`. The `state` it gets is `fetch_rate`'s input, so `state["weight_kg"]` and `state["zone"]` are there.
  - When does it run? Only after the retry loop has given up. `fetch_rate`'s attempts each run under `RATE_TIMEOUT`, `retry_rate` decides after each failure, and the handler is called once with the last exception. That is why sections 2 and 3 show 4 rate calls but only one handler update.
  - Line 138 is an allowlist: only an outage and a timeout get an estimate. Everything else is re-raised on line 142. In this graph that means `ParcelTooHeavy`. An exception raised by a handler is not caught by another handler (the default one included), so it fails the run and reaches the caller. The handler node also has `RATE_RETRY`, but `retry_rate` returns `False` for `ParcelTooHeavy`, so the handler is not run again.
  - Lines 147–153: the handler returns a `Command`, not a dict. When `fetch_rate` fails, its own edge to `write_reply` (line 229) does not fire. The handler's return value alone decides what comes next. `update` is merged into the state like a node's return value. `goto="write_reply"` schedules the next node. With a plain dict the run would stop after the handler, without a reply.
  - The `Literal["write_reply"]` in the return type is for the reader and a type checker only. On a regular node LangGraph parses a `Command[Literal[...]]` annotation into the node's possible destinations. On a handler node it does not: the handler node gets no destinations at all, and `get_graph()` would draw `__error_handler__fetch_rate` with no edges. Routing comes only from `goto`, which is why the module docstring (lines 5–6) spells out the handler paths in words.
- [`record_failure`](../src/l10_3_error_handlers/graph.py#L156-L162) is the default handler. It does not try to fix anything. It records the failure and jumps to `write_reply`. When `lookup_zone` fails, this skips `fetch_rate`, which could not run without a zone anyway.
  - It also covers `write_reply`. If `write_reply` failed, `record_failure` would send the run to `write_reply` again. This never happens here, because `write_reply` only formats strings.
- Both handlers are `async def` (comment on lines 128–129). LangGraph turns each handler into a graph node, and the default timeout also applies to those nodes. A sync handler would make `compile()` raise the same `ValueError` as a sync node.

### build_graph (lines 168–236)

- [`lookup_zone`](../src/l10_3_error_handlers/graph.py#L181-L183) only changed from `def` to `async def`. The body still calls the sync `api.lookup_zone`, which returns at once, so nothing has to be awaited. With a default timeout there is no way to leave one node untimed: `timeout=None` in `add_node` means "use the default".
- [`write_reply`](../src/l10_3_error_handlers/graph.py#L195-L204) works out what happened from which keys exist:
  - no `price`: the default handler ran before `fetch_rate` (section 4);
  - `price` and `error`: `fallback_quote` wrote an estimate (sections 2 and 3);
  - otherwise: a real price (section 1).
  The order of the checks matters. In section 4 `error` is there too, so the `price` check has to come first.
- [`builder.set_node_defaults`](../src/l10_3_error_handlers/graph.py#L215-L219) stores the defaults on the builder. They are applied in `compile()` on line 233, to every node that did not set the value itself in `add_node`. So the call could also come after the `add_node` lines. In the compiled graph:
  - `lookup_zone`, `fetch_rate` and `write_reply` get `RATE_RETRY` and `RATE_TIMEOUT`;
  - `lookup_zone` and `write_reply` get `record_failure` as their handler;
  - the two handler nodes, `__error_handler__fetch_rate` and `__default_error_handler__`, get the retry and timeout too, but no handler and no cache policy.
  [`test_node_defaults_on_the_compiled_graph`](../tests/test_error_handlers.py#L43-L58) checks exactly this list.
- Line 220: `lookup_zone` sets only `cache_policy`. The cache is per node and is not one of the defaults here.
- Line 224: `error_handler=fallback_quote` wins over `record_failure` for this node. LangGraph registers the handler as an extra node named `__error_handler__fetch_rate`, and that is the name under which its update shows up in the stream.
- Lines 227–230: the edges describe only the healthy path. The paths through the handlers are not edges. They come from the `goto` in each handler's `Command`.

## [\_\_main\_\_.py](../src/l10_3_error_handlers/__main__.py)

Five quotes against one `ShippingApi` and one graph with an `InMemoryCache`. Every section uses a different city, so the cache never answers in this run.

- [`show_quote`](../src/l10_3_error_handlers/__main__.py#L13-L20) works as before. Failed attempts print nothing. A handler prints its update under its node name.
- [Section 1](../src/l10_3_error_handlers/__main__.py#L34-L35): three updates, one per node. This is the only run where the edge from `fetch_rate` to `write_reply` is used.
- [Section 2](../src/l10_3_error_handlers/__main__.py#L37-L47): 10 scripted outages, 4 attempts, then `fallback_quote` with the fourth `RateServiceUnavailable`. There is no `fetch_rate` line in the output, and no `attempts` key: the node never returned. The estimate is 3.0 kg × 9.0 = 27.0.
- [Section 3](../src/l10_3_error_handlers/__main__.py#L49-L57): line 52 clears the 6 outages left over from section 2. Otherwise the first attempts here would be outages, not hangs. Every attempt is cut off by the idle timeout, and the handler gets a `NodeTimeoutError`. The output is the same shape as section 2. The error type is the only thing that shows a timeout happened, because `describe_failure` leaves out the message with the elapsed time.
- [Section 4](../src/l10_3_error_handlers/__main__.py#L59-L68): Rome is not in `ZONES`, so `lookup_zone` raises `KeyError`. There is no `lookup_zone` line, the first update is `__default_error_handler__`, and `rate service calls: 0` shows that `fetch_rate` was skipped.
- [Section 5](../src/l10_3_error_handlers/__main__.py#L70-L79): `lookup_zone` succeeds, `fetch_rate` raises `ParcelTooHeavy` after one call, and `fallback_quote` re-raises it. The handler node prints nothing because it raised instead of returning an update. The `except ParcelTooHeavy` on line 75 catches the original exception class, not a LangGraph wrapper.

## [test_error_handlers.py](../tests/test_error_handlers.py)

Plain sync tests as in 10.2. Each builds its own `ShippingApi` and a graph without a cache.

- [`test_healthy_quote_gets_a_reply`](../tests/test_error_handlers.py#L9-L15): `"error" not in result` shows that no handler ran.
- [`test_outage_ends_in_an_estimate_from_the_node_handler`](../tests/test_error_handlers.py#L18-L28): line 27 checks that `attempts` is missing. That proves `fetch_rate` never finished and the price came from the handler.
- [`test_unknown_city_is_caught_by_the_default_handler`](../tests/test_error_handlers.py#L31-L40): `zone_lookups == 1` checks the retry decision, and `rate_calls == 0` checks the jump over `fetch_rate`.
- [`test_node_defaults_on_the_compiled_graph`](../tests/test_error_handlers.py#L43-L58) reads the compiled nodes from `graph.nodes`, handler nodes included. The compiled node keeps `retry_policy` as a tuple, so it is compared with `(RATE_RETRY,)`.

## [test_graph.py](../tests/test_graph.py) and [test_timeouts.py](../tests/test_timeouts.py)

The 10.2 tests with the new package name. The three tests that used to expect an exception now check what the handler wrote, and they still count calls, so the retry behaviour is pinned down as before. [`test_run_timeout_is_a_hard_cap_and_not_retried`](../tests/test_timeouts.py#L44-L52) shows that a timeout `retry_rate` refuses still reaches the handler, after 1 call. [`test_errors_outside_retry_on_are_not_retried`](../tests/test_graph.py#L30-L36) is unchanged and still expects `ParcelTooHeavy`, which only passes because `fallback_quote` re-raises it.

# 10.2 Node Timeouts — code walkthrough

The quote graph from 10.1, `lookup_zone -> fetch_rate`, now has a `TimeoutPolicy` on `fetch_rate`. The scripted rate service can now also hang or be slow. Four quotes in a row show four cases: an idle timeout cuts off a hang and a retry recovers, heartbeats keep a slow call alive, a permanent hang uses up every retry, and a call that keeps reporting progress still hits the hard run timeout. Run it with `./run.sh 10.2` from the course root. The whole run takes about two seconds.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 10.1

- [`STEP_S` and `HANG_S`](../src/l10_2_node_timeouts/service.py#L32-L36), the new [`rate_hangs` and `rate_steps`](../src/l10_2_node_timeouts/service.py#L43-L55) arguments of `ShippingApi`, and the hang and slow paths in [`get_rate`](../src/l10_2_node_timeouts/service.py#L66-L97), which now also takes an `on_progress` callback.
- [`retry_rate`](../src/l10_2_node_timeouts/graph.py#L32-L46) is new, and [`RATE_RETRY`](../src/l10_2_node_timeouts/graph.py#L63) now uses it as `retry_on` instead of the plain `RateServiceUnavailable` class.
- [`RATE_TIMEOUT`](../src/l10_2_node_timeouts/graph.py#L67-L82) is new, in a new `timeout_policy` region.
- [`fetch_rate`](../src/l10_2_node_timeouts/graph.py#L118) passes `runtime.heartbeat` to the service, and the node is [added](../src/l10_2_node_timeouts/graph.py#L131) with `timeout=RATE_TIMEOUT`.
- [`__main__.py`](../src/l10_2_node_timeouts/__main__.py#L34-L92) has four new sections. The comment about a sync `invoke()` now names a `ValueError` instead of a `TypeError`.
- [`test_timeouts.py`](../tests/test_timeouts.py) is new. `test_graph.py` is the 10.1 file with only the package name changed.

## [service.py](../src/l10_2_node_timeouts/service.py)

The fake shipping API. It still knows nothing about LangGraph. It now has two new ways to misbehave, and a progress callback that the graph can hook into.

- [`STEP_S`](../src/l10_2_node_timeouts/service.py#L33) and [`HANG_S`](../src/l10_2_node_timeouts/service.py#L36) set the timing. A step of 0.025 s is a quarter of the 0.1 s idle timeout, so a slow call reports progress about four times in each idle window. `HANG_S` is never really waited for, because the timeout cancels the sleep after 0.1 s. Remove the timeout and you see a 5-second stall per hung call instead of a frozen program.
- [`ShippingApi.__init__`](../src/l10_2_node_timeouts/service.py#L43-L57): `rate_hangs` is a countdown like `rate_failures`, and one hung call uses up one hang. `rate_steps` is different: it applies to every call until someone changes it. That is why `__main__.py` sets it back to 0 in section 3.
- [`get_rate`](../src/l10_2_node_timeouts/service.py#L66-L97) checks things in a fixed order. It counts the call (line 78), checks the weight, then the scripted outage, then the hang, then the slow path. So a hung call is counted in `rate_calls` before it hangs, and a cancelled attempt still shows up in the counter.
  - Line 90: `await asyncio.sleep(HANG_S)` is the hang. When LangGraph's timeout fires, it cancels the task that runs the node. The `CancelledError` comes out of this `await`, so the call never reaches its `return`.
  - Lines 93–96: the slow path. Each step is a real `await`, so the event loop stays free and LangGraph's timeout watchers can run in the meantime. `on_progress()` is called after every step. The service has no idea what the callback does. In this lesson it is `runtime.heartbeat`.
  - Note that a hang also runs the slow path afterwards if `rate_steps > 0`. The demo never mixes the two: section 3 resets `rate_steps` to 0 and section 4 clears `rate_hangs`. Under a timeout the slow path after a hang would not be reached anyway, because the timeout cuts the hang off first.

## [graph.py](../src/l10_2_node_timeouts/graph.py)

The state, the retry decision, the two policies on `fetch_rate`, the cache policy on `lookup_zone`, and the wiring. `QuoteState`, `zone_cache_key`, `ZONE_CACHE` and `lookup_zone` are the same as in 10.1.

- [`retry_rate`](../src/l10_2_node_timeouts/graph.py#L32-L46) is the function form of `retry_on`. The retry loop calls it with the exception the attempt raised. `True` means: wait the backoff interval and try again. `False` means: re-raise at once.
  - A timeout reaches this function as an ordinary exception. LangGraph runs the timeout inside the same retry loop that runs the node, so a `NodeTimeoutError` goes through `retry_on` like any error the node raises itself.
  - Line 45: `error.kind` is `"idle"` or `"run"`, depending on which limit fired. This is the only place in the lesson that treats the two differently.
  - Line 46: everything that is not a timeout keeps the 10.1 rule. That is why the 10.1 tests in `test_graph.py` still pass unchanged: 4 calls for a long outage, 1 call for a 40 kg parcel.
  - Without a custom `retry_on`, `default_retry_on` would retry both kinds of timeout. The comment on lines 42–43 explains why: `NodeTimeoutError` subclasses `Exception`, not the built-in `TimeoutError`, which is an `OSError`.
- [`RATE_RETRY`](../src/l10_2_node_timeouts/graph.py#L50-L64) has the same numbers as in 10.1: 4 attempts and waits of 0.05, 0.1 and 0.2 s. Only the `retry_on` line (63) and its comment changed.
- [`RATE_TIMEOUT`](../src/l10_2_node_timeouts/graph.py#L70-L79) is, like `RetryPolicy`, only a set of settings until it is attached on line 131. For each attempt LangGraph runs the node body as a background task and starts one watcher per limit. If a watcher finishes first, LangGraph cancels the node task and raises `NodeTimeoutError` with the node name, the limit that fired and its value.
  - Line 72: `run_timeout=0.3` counts from the start of the attempt, and nothing resets it.
  - Line 78: `idle_timeout=0.1` counts from the last progress signal. `refresh_on` is not set, so it keeps its default `"auto"`. `fetch_rate` has no writes before it returns, no stream output and no LangChain calls, so in practice only the heartbeats count.
  - Both limits apply to one attempt (lines 68–69). Four idle attempts take 4 × 0.1 s plus the backoff, not 0.1 s in total.
- [`build_graph`](../src/l10_2_node_timeouts/graph.py#L102-L137):
  - Line 118: `on_progress=runtime.heartbeat` passes the bound method itself, not the result of calling it. The service calls it later, from inside its loop. During an attempt with an idle timeout LangGraph swaps in a `runtime` whose `heartbeat` resets the idle clock. Otherwise (no timeout, or a run timeout only) it is a function that does nothing, so the same node also works without a timeout.
  - Line 122: `node_attempt` counts timed-out attempts as well. In section 1 the hung first attempt counts as 1, so the answer reports `attempts: 2`.
  - Line 131: `timeout=` sits next to `retry_policy=`. Both are per node. `lookup_zone` gets neither. It is a sync function, and LangGraph can only time async nodes, because it stops a node by cancelling its asyncio task. `add_node` accepts a timeout on a sync node, but `compile()` on line 137 then raises `ValueError`.

## [\_\_main\_\_.py](../src/l10_2_node_timeouts/__main__.py)

Four quotes against one `ShippingApi` and one graph. Each section changes the service script before it runs.

- [`show_quote`](../src/l10_2_node_timeouts/__main__.py#L15-L20) is unchanged from 10.1. Sections 1 and 2 use it, so you see the node updates. A timed-out attempt produces no update. Only the attempt that succeeds does.
- Lines 28–32: the graph is run with `astream`/`ainvoke` only. A sync `invoke()` now fails at the timed node with the `ValueError` quoted in the comment, instead of 10.1's `TypeError`.
- Section 1 (lines 34–39): the first call sleeps on line 90 of `service.py`. It sends no heartbeat, so after 0.1 s the idle watcher fires and the attempt is cancelled. `retry_rate` returns `True`, LangGraph waits 0.05 s, and the second call answers at once. The output:
  `{'fetch_rate': {'price': 8.0, 'attempts': 2}}` and `rate service calls: 2`.
- Section 2 (lines 42–54): 8 steps take 0.2 s, longer than the idle timeout, but there is a heartbeat every 0.025 s. One attempt is enough, so the output shows `{'fetch_rate': {'price': 12.0, 'attempts': 1}}` and `took longer than idle_timeout=0.1 s: True`. The last line prints a comparison rather than the measured time, so it reads the same on every machine. The 0.2 s is also below the 0.3 s run timeout. With about 12 steps (0.3 s of work) or more, this section would hit the run timeout.
- Section 3 (lines 57–73): `rate_steps` goes back to 0 (line 58), so each hung call is silent, and there are 10 scripted hangs for 4 attempts. Every attempt ends with an idle timeout, and after the fourth LangGraph re-raises that last `NodeTimeoutError` itself. The `except` on line 63 catches it by its own class. `except TimeoutError` would not catch it. Line 60 counts calls from here on, because the API object is shared with the earlier sections. The output is `gave up after 4 calls: idle timeout of 0.1 s in fetch_rate`.
- Section 4 (lines 76–92): line 78 clears the 6 hangs left over from section 3. With 40 steps the call would work for 1 s and send a heartbeat the whole time, so the idle watcher never fires. The run watcher fires at 0.3 s anyway. `retry_rate` returns `False` for `kind == "run"`, so there is no backoff and no second call: `gave up after 1 call: run timeout of 0.3 s in fetch_rate`.
- Lines 71–72 and 90–91 print only `kind`, `timeout` and `node`. `str(error)` and `error.elapsed` contain the measured time (for example `elapsed: 0.101s`), which changes from run to run.

## [test_timeouts.py](../tests/test_timeouts.py)

Plain sync pytest functions, as in 10.1. Each one builds its own `ShippingApi` and a graph without a cache, so no counters or scripts leak between tests.

- [`test_idle_timeout_cuts_off_a_hang_and_retry_recovers`](../tests/test_timeouts.py#L15-L22) is section 1: two calls, and the state reports attempt 2.
- [`test_heartbeats_keep_a_slow_call_alive`](../tests/test_timeouts.py#L25-L32) checks `rate_calls == 1`. A passing quote alone would not prove much, because a retry could also produce one. The counter shows that the first attempt was never cut off.
- [`test_permanent_hang_exhausts_retries`](../tests/test_timeouts.py#L35-L44) checks the fields of the error that reaches the caller, and that `max_attempts=4` also limits timed-out attempts. At about 0.75 s it is the slowest test.
- [`test_run_timeout_is_a_hard_cap_and_not_retried`](../tests/test_timeouts.py#L47-L55): `kind == "run"` and a single call together show both points of section 4.
- [`test_retry_rate_decisions`](../tests/test_timeouts.py#L58-L65) calls `retry_rate` directly, without a graph. It builds `NodeTimeoutError` by hand. The constructor needs the limit that matches `kind` (`idle_timeout=` for `"idle"`, `run_timeout=` for `"run"`) and raises `ValueError` without it. Line 65 pins down the class detail the whole retry decision depends on.

## [test_graph.py](../tests/test_graph.py)

The 10.1 tests with only the package name changed. They now also check that adding `retry_rate` and the timeout did not change how outages, bad requests and the cache behave.

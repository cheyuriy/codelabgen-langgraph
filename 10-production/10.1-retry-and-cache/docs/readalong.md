# 10.1 Retry and Cache Policies — code walkthrough

The program quotes a shipping price in two steps, `lookup_zone -> fetch_rate`. The rate step talks to a scripted, flaky service and is retried with a `RetryPolicy`. The zone step stands for an expensive address lookup and is cached with a `CachePolicy` and an `InMemoryCache`. Four quotes in a row show a retry that recovers, a cache hit, retries that run out, and an error that is never retried. Run it with `./run.sh 10.1` from the course root.
The concept itself is explained in the [notes](notes.md).

## [service.py](../src/l10_1_retry_and_cache/service.py)

A fake shipping API. Nothing in it knows about LangGraph. It exists so the graph has something to retry and something worth caching, and its counters let you see how often each call really ran.

- [`RateServiceUnavailable`](../src/l10_1_retry_and_cache/service.py#L9-L13) and [`ParcelTooHeavy`](../src/l10_1_retry_and_cache/service.py#L16-L20) are the two kinds of failure the lesson is about: one that may go away if you wait, and one that never will. The base classes matter. `ConnectionError` is what LangGraph's built-in `default_retry_on` treats as retryable, and `ValueError` is one of the errors it never retries. So even without the explicit `retry_on` in `graph.py`, these two would be handled the same way: delete `retry_on` and sections 3 and 4 still behave as before.
- [`ZONES`, `RATES_PER_KG`, `MAX_WEIGHT_KG`](../src/l10_1_retry_and_cache/service.py#L25-L27) are the whole "database". London at 4.0 per kg gives the 8.0 and 20.0 prices you see in the output.
- [`ShippingApi.__init__`](../src/l10_1_retry_and_cache/service.py#L34-L42): `rate_failures` is the outage script. `__main__.py` changes it between sections to switch the service "down" and "up". `zone_lookups` and `rate_calls` are the only way to tell a cache hit from a real call and to count retries from outside the graph.
- [`lookup_zone`](../src/l10_1_retry_and_cache/service.py#L44-L49) counts first (line 46), then works. Line 48 takes the city after the last comma, so `"  12 baker street, LONDON "` and `"12 Baker Street, London"` give the same zone. That is why the cache key in `graph.py` may safely treat them as one address.
- [`get_rate`](../src/l10_1_retry_and_cache/service.py#L51-L61) is `async` because it stands for a network call. It also counts on entry (line 53), so every retry LangGraph makes shows up in `rate_calls`. The weight check on line 56 comes before the outage check on line 58: a 40 kg parcel raises `ParcelTooHeavy` even while the service is "down", and it does not use up one of the scripted failures.

## [graph.py](../src/l10_1_retry_and_cache/graph.py)

The state, the two policies, the two nodes and the wiring.

- [`QuoteState`](../src/l10_1_retry_and_cache/graph.py#L17-L24) is a plain `TypedDict` with no reducers. Each key is written by one node only. `attempts` (line 24) is there only so the output shows which attempt succeeded.
- [`RATE_RETRY`](../src/l10_1_retry_and_cache/graph.py#L31-L44) is just a `NamedTuple` of settings. It does nothing until it is attached to a node on line 90. When the node raises, LangGraph checks the exception against `retry_on`. If it matches and attempts are left, it waits `initial_interval * backoff_factor ** (n - 1)` seconds (capped by `max_interval`, 128 s by default) and runs the node again. Otherwise it re-raises the node's own exception.
  - Line 33: the defaults would be 3 attempts and 0.5 s. They are set explicitly so the numbers in the output are easy to follow: 4 attempts, waits of 0.05 + 0.1 + 0.2 = 0.35 s.
  - Line 41: `jitter` defaults to `True`. With it on, every wait gets a random extra 0 to 1 s, which would make this demo slow and its timing different on each run.
  - Line 43: a single exception class. `retry_on` also accepts a list of classes or a function `exc -> bool`. If you leave it out, LangGraph uses `default_retry_on`.
- [`zone_cache_key`](../src/l10_1_retry_and_cache/graph.py#L49-L56) gets the node's input, which is the whole state here. Whatever it returns is hashed (xxh3) into the cache key. LangGraph also puts the node name into the key's namespace, so two cached nodes never share entries even when their keys are equal. Two inputs that give the same string share one entry, so the function must cover everything the result depends on. Here that is only the address.
- [`ZONE_CACHE`](../src/l10_1_retry_and_cache/graph.py#L60): without `key_func`, the default key pickles the whole input, so a different `weight_kg` would be a different key and section 2 would miss.
- [`build_graph`](../src/l10_1_retry_and_cache/graph.py#L65-L96) takes the API as an argument, so each test can pass its own `ShippingApi` with its own counters and outage script.
  - [`lookup_zone`](../src/l10_1_retry_and_cache/graph.py#L73-L75) and [`fetch_rate`](../src/l10_1_retry_and_cache/graph.py#L77-L83) are nested so they close over `api`. LangGraph only ever passes them the state, plus `runtime` for `fetch_rate`.
  - `lookup_zone` is a sync function and `fetch_rate` is async. LangGraph runs both kinds in one graph, but a graph with an async node has to be run with `ainvoke`/`astream`.
  - Line 83: `runtime.execution_info.node_attempt` is filled in by the retry loop for each attempt: 1, 2, 3, ... The node itself does not have to count anything. In section 1 the third attempt succeeds, so `attempts` is 3.
  - A retry reruns only the failing node, with the same input. `lookup_zone` already finished in the step before and is not called again.
  - Lines 89–90: both policies are per node and go in as `add_node` keyword arguments. `lookup_zone` has no retry policy and `fetch_rate` is not cached. Caching a price that depends on a live service would be a different decision.
  - Line 96: `compile(cache=cache)` is where the backend comes in. The default `None` is valid, so `build_graph(api)` gives a graph that never caches. `test_cache_policy_without_backend_does_nothing` checks exactly that.

## [\_\_main\_\_.py](../src/l10_1_retry_and_cache/__main__.py)

Four quotes against one API object and one graph, so both the outage script and the cache carry over from one section to the next.

- [`show_quote`](../src/l10_1_retry_and_cache/__main__.py#L17-L22) streams with `stream_mode="updates"` rather than calling `ainvoke`, because only the update stream shows the `'__metadata__': {'cached': True}` marker on a node answered from the cache. `ainvoke` returns the same final state either way.
- Line 32: one `InMemoryCache` for the whole run. It lives in process memory, so it is empty again on the next `./run.sh`.
- Section 1 (lines 34–36): the first two calls raise `RateServiceUnavailable` and the third succeeds, so you see a single `fetch_rate` update with `attempts: 3`. The failed attempts produce no updates; they only show up in `rate service calls: 3`. This section waits 0.05 + 0.1 s in backoff.
- Section 2 (lines 39–41): the address normalises to the same key as in section 1, so LangGraph takes `lookup_zone`'s stored writes from the cache instead of calling the function, and `zone lookups` stays at 1. `fetch_rate` still runs with the new weight, so the price is 20.0.
- Section 3 (lines 44–51): ten scripted failures are more than four attempts. After the fourth, LangGraph re-raises the node's original `RateServiceUnavailable`, so the `except` on line 49 can catch the real error class and message, not a LangGraph wrapper.
- Section 4 (lines 54–62): `ParcelTooHeavy` does not match `retry_on`, so the first failure goes straight to the caller with no backoff wait.
- Line 66: `zone lookups in total: 2`, from London in section 1 and Paris in section 3. Section 4 got the Paris zone from the cache, although the run in section 3 failed. LangGraph saves a node's writes to the cache as soon as that node succeeds, so a later failure of another node in the same run does not remove them.
- Line 70: `asyncio.run(main())`, because the graph has an async node. A sync `graph.invoke` would fail with `TypeError: No synchronous function provided to "fetch_rate"`.

## [test_graph.py](../tests/test_graph.py)

Plain sync pytest functions that drive the async graph with `asyncio.run`. Each test makes its own `ShippingApi` and graph, so no counter or cache entry leaks from one test into another.

- [`test_retry_recovers_from_transient_failures`](../tests/test_graph.py#L15-L22) checks that the state reports the third attempt and that the service saw three calls. It runs without a cache, because retries do not need one.
- [`test_retries_stop_at_max_attempts`](../tests/test_graph.py#L25-L31): line 31 shows that `max_attempts=4` means four calls in total, not four retries.
- [`test_errors_outside_retry_on_are_not_retried`](../tests/test_graph.py#L34-L40) pins down the single call for a bad request.
- [`test_cache_hit_for_same_address_in_other_spelling`](../tests/test_graph.py#L43-L61) changes both the spelling and the weight, so it tests both halves of `zone_cache_key`: normalising the address and ignoring the weight. Line 61 checks the stream marker, not just the counter.
- [`test_cache_policy_without_backend_does_nothing`](../tests/test_graph.py#L64-L71) runs two identical requests without a backend and gets two lookups. No error, no warning, only the counter shows it.

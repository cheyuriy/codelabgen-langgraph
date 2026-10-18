# 10.4 Recovering a Failed Run — code walkthrough

The quote graph from 10.3 now also ships the parcel. After `fetch_rate`, two nodes run in parallel: one books a courier pickup and one prints the label. The graph is compiled with a checkpointer. When the label printer goes offline, the run fails, the printer is switched back on, and the run continues from its last checkpoint. Only the failed node runs again. Run it with `./run.sh 10.4` from the course root. The whole run takes well under a second.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 10.3

- `service.py`: the new error [`LabelPrinterOffline`](../src/l10_4_recover_failed_run/service.py#L28-L33), three new counters and flags in [`ShippingApi.__init__`](../src/l10_4_recover_failed_run/service.py#L67-L69), and the sync methods [`book_pickup`](../src/l10_4_recover_failed_run/service.py#L79-L87) and [`print_label`](../src/l10_4_recover_failed_run/service.py#L89-L98).
- `graph.py`: the import [`BaseCheckpointSaver`](../src/l10_4_recover_failed_run/graph.py#L15). [`QuoteState`](../src/l10_4_recover_failed_run/graph.py#L35-L36) gains `pickup_id` and `label_id`.
- [`record_failure`](../src/l10_4_recover_failed_run/graph.py#L164-L174) is no longer the graph-wide default handler. It moved from [`set_node_defaults`](../src/l10_4_recover_failed_run/graph.py#L252-L255) to [`lookup_zone`'s `add_node`](../src/l10_4_recover_failed_run/graph.py#L258-L260). Its code is unchanged.
- [`fallback_quote`](../src/l10_4_recover_failed_run/graph.py#L148-L150) is unchanged apart from a comment at the `raise`.
- New nodes [`book_pickup` and `print_label`](../src/l10_4_recover_failed_run/graph.py#L215-L229), [registered](../src/l10_4_recover_failed_run/graph.py#L265-L266) without an error handler.
- The edge `fetch_rate -> write_reply` is replaced by the [fan-out and join](../src/l10_4_recover_failed_run/graph.py#L277-L279) through the two new nodes.
- [`build_graph`](../src/l10_4_recover_failed_run/graph.py#L181-L185) takes a `checkpointer` and passes it to [`compile`](../src/l10_4_recover_failed_run/graph.py#L285).
- [`__main__.py`](../src/l10_4_recover_failed_run/__main__.py) is rewritten: one `InMemorySaver`, a `config` with a `thread_id` for every run, the new helper `show_saved` and five new sections.
- [`test_recovery.py`](../tests/test_recovery.py) is new. In [`test_error_handlers.py`](../tests/test_error_handlers.py), the unknown-city test is renamed and [`test_node_defaults_on_the_compiled_graph`](../tests/test_error_handlers.py#L43-L68) checks the new node list. `test_graph.py` and `test_timeouts.py` only have the new package name.

## [service.py](../src/l10_4_recover_failed_run/service.py)

The simulated shipping service. `lookup_zone` and `get_rate` work as in 10.3.

- [`LabelPrinterOffline`](../src/l10_4_recover_failed_run/service.py#L28-L33) is a `RuntimeError`, not a `ConnectionError`. `retry_rate` in `graph.py` retries only `RateServiceUnavailable` and idle timeouts, so this error fails the node at the first attempt. That is on purpose: a person has to fix this cause, and retrying a few milliseconds later would not help.
- [`printer_online`](../src/l10_4_recover_failed_run/service.py#L67) is the switch that `__main__.py` and the tests flip to script the outage and the fix. `pickups_booked` and `labels_printed` count the side effects, so the output can show that nothing was done twice.
- [`book_pickup`](../src/l10_4_recover_failed_run/service.py#L79-L87) returns `PU-<n>`, where `n` is the number of pickups booked so far. A second booking would print a new id, so a repeated side effect is visible in the output.
- [`print_label`](../src/l10_4_recover_failed_run/service.py#L89-L98) raises on line 96 while the printer is off, before it counts anything.
- Both methods are sync and never sleep. In the parallel step, `book_pickup` therefore always finishes before `print_label` raises, and every run gives the same output. If `book_pickup` were still running when `print_label` failed, LangGraph would cancel it, and the resume would run it again.

## [graph.py](../src/l10_4_recover_failed_run/graph.py)

The state, the policies and handlers from 10.3, the two shipment nodes and the wiring. `retry_rate`, `RATE_RETRY`, `RATE_TIMEOUT`, `ZONE_CACHE`, `describe_failure`, `lookup_zone`, `fetch_rate` and `write_reply` work as in 10.3.

- [`QuoteState`](../src/l10_4_recover_failed_run/graph.py#L25-L36): the two new keys each have one writer. `book_pickup` and `print_label` run in the same step, and each writes a different key. That is why the state needs no reducer here: two writes to the same plain key in one step would raise `InvalidUpdateError`.

### The error handlers (lines 118–177)

- [`fallback_quote`](../src/l10_4_recover_failed_run/graph.py#L136-L161) still re-raises `ParcelTooHeavy` on line 150. The new comment on lines 148–149 is about what this does to the thread. When a handler re-raises the original exception, LangGraph 1.2.16 saves the failed step as finished. `next` is empty afterwards, so there is nothing to resume. Section 5 of the run shows this.
- [`record_failure`](../src/l10_4_recover_failed_run/graph.py#L168-L174) has the same body as in 10.3. Only its place changed. The comment on lines 164–167 gives the reason:
  - A default handler from `set_node_defaults` would also cover `book_pickup` and `print_label`.
  - In 1.2.16 a resume never runs a node that has an error handler again. If a handler raises a new exception, the resume runs the handler again, never the node. So a node that should be fixed and resumed must have no handler at all.
  - `add_node(..., error_handler=None)` does not turn a default off, it means "use the default". The only way to leave the shipment nodes without a handler is to have no default.

### build_graph (lines 180–288)

- [The signature](../src/l10_4_recover_failed_run/graph.py#L181-L185): `checkpointer` defaults to `None`, so `build_graph(api)` compiles a graph without a checkpointer, as in 10.3. That is why `test_graph.py`, `test_timeouts.py` and `test_error_handlers.py` still call `ainvoke` without a config. A graph with a checkpointer needs `{"configurable": {"thread_id": ...}}` on every call, or it raises `ValueError`.
- [`book_pickup` and `print_label`](../src/l10_4_recover_failed_run/graph.py#L221-L227) only call the API and return one key each. They are `async def` for the same reason as every node since 10.3: the default timeout covers them, and a timed node must be async. They do not catch anything, so `LabelPrinterOffline` leaves the node unchanged.
- [`set_node_defaults`](../src/l10_4_recover_failed_run/graph.py#L252-L255) now sets only `retry_policy` and `timeout`. Both shipment nodes get them. `retry_rate` returns `False` for `LabelPrinterOffline`, so `print_label` runs once and fails.
- [Lines 258–260](../src/l10_4_recover_failed_run/graph.py#L258-L260): with `error_handler=record_failure` on its own `add_node`, the handler node is named `__error_handler__lookup_zone`, built the same way as `__error_handler__fetch_rate` on line 264. An unknown city still ends in `"no quote (KeyError in lookup_zone)"`, only the handler node's name in the stream is different.
- [Lines 265–266](../src/l10_4_recover_failed_run/graph.py#L265-L266) register the shipment nodes with no extra arguments: the retry and the timeout come from the defaults, and they have no handler.
- [Lines 277–279](../src/l10_4_recover_failed_run/graph.py#L277-L279), the `parallel_edges` region:
  - Lines 277 and 278 are two edges out of `fetch_rate`. After `fetch_rate` finishes, LangGraph schedules both targets for the next super-step, and runs them at the same time.
  - Line 279, `add_edge(["book_pickup", "print_label"], "write_reply")`, adds a join: `write_reply` runs only after both nodes have written. With two separate edges into `write_reply` it would run after each of them.
  - The handler paths still jump straight to `write_reply` with `goto`, so an estimate or a "no quote" never books a pickup.
  - `fetch_rate` keeps a step of its own. The bug #8277 from 10.3 only hits the handler of a node that shares its step with other nodes, so `fallback_quote` keeps working.
- [Line 285](../src/l10_4_recover_failed_run/graph.py#L285): `compile(cache=..., checkpointer=...)`. From now on the graph saves a checkpoint for the thread named in the config after every step. When a node in a step finishes, its writes are saved too, as *pending writes* of that step. On a resume these saved writes are used again instead of running the node.

## [\_\_main\_\_.py](../src/l10_4_recover_failed_run/__main__.py)

Five runs against one `ShippingApi`, one `InMemoryCache` and one `InMemorySaver`. Each run uses its own `thread_id`, so the threads stay separate inside the one checkpointer.

- [`show_quote`](../src/l10_4_recover_failed_run/__main__.py#L15-L26) now takes a `config`. Its `request` can be `None`. `astream(None, config)` means "no new input": LangGraph loads the latest checkpoint of the thread and continues from the tasks that are still open.
- [`show_saved`](../src/l10_4_recover_failed_run/__main__.py#L30-L47): `aget_state` on line 34 returns a `StateSnapshot` of the latest checkpoint.
  - `snapshot.next` holds the names of the tasks that still have to run.
  - `snapshot.tasks` has one `PregelTask` per task of that step. The [loop on lines 41–47](../src/l10_4_recover_failed_run/__main__.py#L41-L47) sorts each task into one of three cases.
  - Line 42, a failed task: it has its error, but as a string. The error went through the checkpointer's serializer, so it is the exception's repr, not an exception you could raise again.
  - Line 44, a kept task: its saved writes are in `result`. "Kept" means "has a saved result", not "has no error". Under `durability="exit"` a sibling that was cancelled when the other task failed is saved with neither an error nor a result, because its `CancelledError` is never written. It is still in `next` and runs again.
  - Line 46, the `else` branch, is that case: nothing saved, the task runs again on resume. In this program's runs it never prints, because `book_pickup` always finishes first.
- [Lines 58–61](../src/l10_4_recover_failed_run/__main__.py#L58-L61) create the checkpointer and pass it to `build_graph`. A sync `invoke()` would still fail, because the handler nodes are async. The comment now names `__error_handler__lookup_zone`, since `__default_error_handler__` no longer exists.
- [Section 1](../src/l10_4_recover_failed_run/__main__.py#L63-L65): a healthy run. `book_pickup` and `print_label` each print an update from the same super-step, then `write_reply` answers once.
- [Section 2](../src/l10_4_recover_failed_run/__main__.py#L69-L79): line 71 switches the printer off.
  - `book_pickup` finishes and its update is streamed. Then `print_label` raises, and with no handler the exception leaves `astream` and is caught on line 74.
  - Before the exception reaches the caller, the checkpointer has saved the checkpoint after `fetch_rate` together with `book_pickup`'s pending write and `print_label`'s error.
  - `show_saved` then prints `next=('print_label',)`, the kept `{'pickup_id': 'PU-2'}` and the saved error string.
- [Section 3](../src/l10_4_recover_failed_run/__main__.py#L84-L98): line 87 fixes the cause first. Line 93 resumes the same thread with `None`.
  - LangGraph loads the checkpoint, finds the saved write for `book_pickup` and applies it without calling the node. The stream shows it again with `'__metadata__': {'cached': True}`. That is the replayed pending write, not the node cache: `book_pickup` has no cache policy.
  - Only `print_label` really runs. With both writes present, the join opens and `write_reply` answers `7.5 EUR to EU`.
  - The summary line `rate calls 0, pickups booked 0, labels printed 1` confirms that only the failed node ran.
  - If line 93 passed the original request instead of `None`, a new run would start on the thread, and every node would run again, the pickup included.
- [Section 4](../src/l10_4_recover_failed_run/__main__.py#L103-L134): the same failure three times, with `durability=` passed per call to the failing [`ainvoke` on lines 114–118](../src/l10_4_recover_failed_run/__main__.py#L114-L118) and to the resume on line 130.
  - Line 123: `checkpointer.list(config)` gives all checkpoints of this thread. With `"sync"` and `"async"` there are 4 at the failure: the input, the start, one after `lookup_zone` and one after `fetch_rate`. Each finished step is saved as it ends. With `"exit"` there is 1: LangGraph keeps the steps in memory and saves the last checkpoint and its pending writes only once, when the run exits. Exiting with an exception counts.
  - Line 127 lists the kept tasks with the same test as `show_saved`: `task.result is not None`. A test on `task.error is None` would be wrong under `"exit"`, where a cancelled sibling has no saved error and still runs again. Here `book_pickup` finishes before the failure, so the output is `kept: ['book_pickup']` in every mode.
  - The resume on line 130 books no second pickup in any mode. For an ordinary exception the three modes behave the same. They differ when the process dies, which an `InMemorySaver` cannot show, because it loses everything anyway.
- [Section 5](../src/l10_4_recover_failed_run/__main__.py#L139-L155): the 40 kg Berlin parcel. `fetch_rate` raises `ParcelTooHeavy` and `fallback_quote` re-raises it, so the run fails as in 10.3.
  - `show_saved` prints `next=()` and no tasks: the step counts as finished.
  - The resume on line 154 runs nothing and only returns the saved values. Line 155 prints 0 rate calls.
  - This is the reason the shipment nodes have no handler: a node with a handler cannot be fixed and resumed.

## [test_recovery.py](../tests/test_recovery.py)

Plain sync tests, each with its own `ShippingApi`, `InMemorySaver` and graph, and no cache. All use the thread `"t"` from [`CONFIG`](../tests/test_recovery.py#L14). `graph.get_state` works synchronously with `InMemorySaver`.

- [`fail_with_printer_offline`](../tests/test_recovery.py#L17-L21) is the shared setup: it switches the printer off and expects `LabelPrinterOffline`. Its default `durability="async"` is the same mode LangGraph uses when none is given.
- [`test_resume_reruns_only_the_failed_node`](../tests/test_recovery.py#L24-L53): line 33 shows that `snapshot.values` already contains the finished sibling's `pickup_id`. Line 39 uses `in str(...)` because the saved error is a string. Lines 47–52 check that each of the four API calls happened once in total.
- [`test_resume_before_the_fix_fails_again`](../tests/test_recovery.py#L56-L64): a resume before the fix fails the same way and leaves `next` as it was. The pickup is still booked only once.
- [`test_every_durability_mode_keeps_the_failed_step`](../tests/test_recovery.py#L67-L83) pins down the checkpoint counts from section 4, before and after the resume: 4 and 6 for `"sync"` and `"async"`, 1 and 2 for `"exit"`.
- [`test_sending_the_input_again_starts_over`](../tests/test_recovery.py#L86-L95): the original input instead of `None` books `PU-2` and calls the rate service again.
- [`test_a_reraised_handler_error_closes_the_thread`](../tests/test_recovery.py#L98-L111): the section 5 case. Line 110 compares the whole result: the state only holds the input and the zone, because `fetch_rate` never wrote anything.
- [`test_no_checkpoint_nothing_to_resume`](../tests/test_recovery.py#L114-L118): `None` on a thread without a checkpoint raises `EmptyInputError`. There is nothing to continue, and no input to start with.

## [test_error_handlers.py](../tests/test_error_handlers.py)

- [`test_unknown_city_is_caught_by_lookup_zones_handler`](../tests/test_error_handlers.py#L31-L40) has a new name and docstring and the same assertions. The reply does not name the handler node, so moving the handler changes nothing in the result.
- [`test_node_defaults_on_the_compiled_graph`](../tests/test_error_handlers.py#L43-L68) now covers seven nodes. Line 65 checks that no `__default_error_handler__` node is left. Lines 67–68 read `error_handler_node` on the compiled nodes: `None` means the node has no handler, so its error reaches the caller.

## [test_graph.py](../tests/test_graph.py) and [test_timeouts.py](../tests/test_timeouts.py)

The 10.3 tests with the new package name. They build the graph without a checkpointer, so they run unchanged without a config. Their healthy runs now go through the two shipment nodes too, and the printer is always online there.

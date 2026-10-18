# 9.1 @entrypoint and @task — code walkthrough

The order checks from lesson 3.1 (stock, payment, address), written with the Functional API. Four `@task` functions do the checks, and one `@entrypoint` function calls them and decides "approved" or "on_hold". The program streams Ada's order task by task, prints the decisions for Bob and Cleo, and then shows what the checkpointer saved for Ada's thread. Run it with `./run.sh 9.1` from the course root.
The concept itself is explained in the [notes](notes.md).

This is a new example, "order-workflow". It mirrors 3.1's order checks: the same data, the same detail strings and the same three orders, so the outputs match. Lesson 9.2 builds on it.

## [workflow.py](../src/l9_1_entrypoint_and_task/workflow.py)

The whole workflow: the types, four tasks, a plain helper and the entrypoint. Read it from top to bottom.

- [`STOCK` and `SHIPS_TO`](../src/l9_1_entrypoint_and_task/workflow.py#L14-L15) are the same fixed data as in 3.1. A sku that is not in `STOCK` counts as 0.

### The types

- [`CheckResult`](../src/l9_1_entrypoint_and_task/workflow.py#L19-L24) is what each check task returns. As in 3.1, the `check` field is the name `decide` looks a result up by.
- [`Order`](../src/l9_1_entrypoint_and_task/workflow.py#L27-L34) is the entrypoint's input. It is not a state schema. LangGraph reads the annotation only to build the input JSON schema (`process_order.get_input_jsonschema()` shows `Order`). The values are not validated or coerced, so a wrong key reaches your code as it is.
- [`OrderOutcome`](../src/l9_1_entrypoint_and_task/workflow.py#L37-L43) is the return value. Its docstring says it is "all that the thread's state will hold". This is the main difference from 3.1. There, `OrderState` was a shared dict that every node read and wrote, and `results` needed `operator.add` because two nodes wrote it in the same super-step. Here, each result is a local variable in `process_order`, so there is nothing to merge and no reducer.

### The check tasks

- [`check_stock`](../src/l9_1_entrypoint_and_task/workflow.py#L52-L59) and [`check_payment`](../src/l9_1_entrypoint_and_task/workflow.py#L62-L67) have the same logic as the 3.1 nodes, with two differences. They take plain arguments (`items`, or `total` and `balance`) instead of the state. They return one `CheckResult` and not `{"results": [...]}`, because nothing has to be merged.
- The bare `@task` on lines 52 and 62 wraps the function. It does not change what the function computes, but it changes how it is called: inside an entrypoint, a call schedules the function as a task and returns a future (see `process_order` below). Outside an entrypoint or graph there is nothing to schedule on, so the call raises `RuntimeError` ("Called get_config outside of a runnable context"). [`test_decide_is_a_plain_function`](../tests/test_workflow.py#L151-L153) checks this.
- `@task` also accepts options (`name`, `retry_policy`, `cache_policy`). This lesson uses none of them.

### The address tasks

- [`normalize_address`](../src/l9_1_entrypoint_and_task/workflow.py#L74-L77) returns a plain `str`, the country code ("de" becomes "DE"). A task can return any value, not only a dict, as long as the checkpointer can serialize it. With a checkpointer, every task result is saved, so returning an object of your own class fails with "Type is not msgpack serializable".
- [`check_address`](../src/l9_1_entrypoint_and_task/workflow.py#L80-L85) takes that country as an argument. In 3.1 the dependency was expressed by an edge and an extra super-step. Here, it is the ordinary data flow of the Python code: `process_order` passes the country in.

### The decision

- [`decide`](../src/l9_1_entrypoint_and_task/workflow.py#L95-L103) is the same join logic as 3.1's `decide` node: a dict by check name on line 97 and sorted names on line 100, so the problems always come out as address, payment, stock.
- It is not a task. A plain function called inside an entrypoint simply runs inline. It produces no stream update and no saved result, and it is run again whenever the entrypoint body runs again. That is fine for pure, fast code like this. It can also be called and tested on its own, which [`test_decide_is_a_plain_function`](../tests/test_workflow.py#L135-L150) does with Bob's results in two orders.
- Note that it returns a plain `dict`, only `decision` and `problems`. `process_order` spreads it into the outcome.

### The entrypoint

- [`checkpointer`](../src/l9_1_entrypoint_and_task/workflow.py#L112) is created at module level, because the decorator on line 120 needs it when the module is imported. `__main__.py` and the tests import the same object to read the saved checkpoints.
- [`process_order`](../src/l9_1_entrypoint_and_task/workflow.py#L120-L133): after decoration, `process_order` is no longer a function but a `Pregel` object, the same type `StateGraph.compile()` returns. It has one node, `process_order`, which runs the function body. That is why `invoke`, `stream` and `get_state` work as in lesson 5.1, and why a checkpointer requires a `thread_id` in the config ([`test_thread_id_is_required`](../tests/test_workflow.py#L156-L159)).
- Lines 126–127 create two futures and wait for neither. LangGraph submits both tasks to its thread pool at once, so `check_stock` and `check_payment` run at the same time. [`test_futures_run_concurrently`](../tests/test_workflow.py#L109-L132) proves it with a `threading.Barrier(2)`: each task waits for the other, which can only finish if both are running together.
- Line 130 calls `.result()` right away, because `check_address` needs the country before it can be scheduled. Only the body waits here. The two checks scheduled on lines 126–127 keep running in their threads.
- Line 131 schedules `check_address`, and line 132 collects all three results. The order of the `.result()` calls does not matter: each one returns at once if its task has already finished. If you forget a `.result()` and pass a future to `decide`, line 97 fails with "'Future' object is not subscriptable".
- Line 133 builds the outcome. What the body returns becomes the run's output and the thread's saved value.
- A rule of thumb for the body: create every future you can before the first `.result()`. Calling `.result()` right after each call makes the tasks run one after the other, without any error.

## [\_\_main\_\_.py](../src/l9_1_entrypoint_and_task/__main__.py)

The entry point. [`ADA`, `BOB` and `CLEO`](../src/l9_1_entrypoint_and_task/__main__.py#L5-L25) are the three orders from 3.1. Ada passes all checks, Bob fails all three, Cleo fails only the address.

- [`config_for`](../src/l9_1_entrypoint_and_task/__main__.py#L28-L30) gives each order its own thread. The checkpoints of one order do not mix with another's, and section three can read Ada's thread after Bob and Cleo ran.
- [`show`](../src/l9_1_entrypoint_and_task/__main__.py#L33-L39) turns the values that appear in updates and checkpoints into one line. A `CheckResult` is recognised by its `check` key, an `OrderOutcome` by `decision`, and the country is a plain string.

[`main`](../src/l9_1_entrypoint_and_task/__main__.py#L42-L84) runs three sections.

- **One update per task** ([lines 45–53](../src/l9_1_entrypoint_and_task/__main__.py#L45-L53)): with `stream_mode="updates"`, every task sends a chunk `{task_name: result}` when it finishes. The entrypoint's own chunk, `{"process_order": outcome}`, comes last ([`test_every_task_reports_an_update`](../tests/test_workflow.py#L71-L84) checks it). `decide` has no line in the output, because it is not a task. The three tasks that run concurrently can finish in any order, so line 52 sorts the names to keep the output stable.
- **Decisions** ([lines 57–63](../src/l9_1_entrypoint_and_task/__main__.py#L57-L63)): `invoke` on line 60 returns what the body returned, the `OrderOutcome`. In 3.1, `invoke` returned the whole state, including the input keys and `results`.
- **What the checkpointer saved** ([lines 67–83](../src/l9_1_entrypoint_and_task/__main__.py#L67-L83)):
  - Line 76 lists Ada's checkpoints. `list` returns the newest first, so `reversed` puts them in run order. There are only two: step -1 (`input`) and step 0 (`loop`). The whole body runs in a single node, so the run is one super-step. 3.1's graph would write five checkpoints for the same order.
  - Line 77 reads `pending_writes`, the `(task_id, channel, value)` triples saved with a checkpoint. Each task writes its result to the `__return__` channel as soon as it finishes. These writes belong to the step that is still running, so they hang on the `input` checkpoint. `or []` covers a checkpoint that has no pending writes. This is what makes a failed run resumable: if a task raises, calling `invoke(None, config)` on the same thread runs the body again from the top, but tasks with a saved `__return__` write return it instead of running again.
  - Lines 81–83 show `get_state`. Its `values` is only the return value. The order and the check results are not there (in 3.1 the snapshot held every state key). `next` is empty because the run finished.
  - [`test_task_results_are_checkpointed`](../tests/test_workflow.py#L87-L106) checks the same facts: two checkpoints, four `__return__` writes, and `get_state` equal to the outcome.

## [test_workflow.py](../tests/test_workflow.py)

- [`fresh_config`](../tests/test_workflow.py#L40-L42) adds a uuid to every `thread_id`. All tests share the module-level `checkpointer`, and a reused thread would already hold checkpoints from another test, so the checkpoint count in `test_task_results_are_checkpointed` would be wrong.
- [`test_futures_run_concurrently`](../tests/test_workflow.py#L109-L132) defines its own tasks and an `@entrypoint()` without a checkpointer, so it can call `invoke(0)` without a config. The barrier has a 5-second timeout: if the tasks ran one after the other, the test would fail with `BrokenBarrierError` instead of hanging.

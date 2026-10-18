# 6.1 Pausing with interrupt() and Resuming with Command — code walkthrough

The program sends three refund requests through a small graph. A \$40 refund is approved by policy right away. A \$250 refund pauses inside `manager_review` and waits for a manager. The program reads the pending interrupt from the invoke result and from `get_state`, then resumes the thread with `Command(resume="approved")`. A \$500 refund repeats the pause and resume with the v2 output format. Run it with `./run.sh 6.1` from the course root.
The concept itself is explained in the [notes](notes.md).

## Where the code comes from

This is the first lesson of module 6, and its example ("refund-approval") is new. Lessons 6.2, 6.3 and 6.5 build on it. That is why the checkpointer is a parameter of `build_graph` (the same pattern as 5.1) and why `manager_review` only stores the decision: routing on the answer comes in 6.2.

[pyproject.toml](../pyproject.toml#L6-L9) pins `langgraph==1.2.16` and `langgraph-checkpoint==4.3.0`. The second one is listed because the code imports `InMemorySaver` and `BaseCheckpointSaver` from it directly.

## [refunds.py](../src/l6_1_interrupt_and_resume/refunds.py)

The state, the three functions the graph runs, and `build_graph`. There is no LLM: every node is plain Python, so the run is offline and the output is always the same.

- [Line 13](../src/l6_1_interrupt_and_resume/refunds.py#L13) imports `interrupt` from `langgraph.types`. That module also holds `Command` and `Interrupt`, which `__main__.py` and the tests use.
- [`REFUND_LIMIT`](../src/l6_1_interrupt_and_resume/refunds.py#L16) is the only rule of the policy: amounts up to 100 are approved automatically.
- [`RefundState`](../src/l6_1_interrupt_and_resume/refunds.py#L20-L31) has no reducers, so each key a node returns simply replaces the old value. `status` and `decided_by` on [lines 30-31](../src/l6_1_interrupt_and_resume/refunds.py#L30-L31) are `NotRequired`: the caller sends only `request_id` and `amount`. LangGraph does not fill in missing keys, so a paused request's state has just two keys. You see this in the `values:` line of the output.
- [`route_by_amount`](../src/l6_1_interrupt_and_resume/refunds.py#L38-L44) is the function behind the conditional edge. LangGraph calls it with the current state and runs the node whose name it returns. The `>` on [line 42](../src/l6_1_interrupt_and_resume/refunds.py#L42) means that exactly \$100 still goes to `auto_approve`.
- [`auto_approve`](../src/l6_1_interrupt_and_resume/refunds.py#L51-L53) returns a partial update. LangGraph merges it into the state, so R-1 ends with all four keys.

### [`manager_review`](../src/l6_1_interrupt_and_resume/refunds.py#L60-L86)

The one node that waits for a human. The docstring already describes the two runs. What happens inside the library:

- The print on [line 76](../src/l6_1_interrupt_and_resume/refunds.py#L76) is the visible proof that the node restarts. It runs on the first run and again on resume, so the output shows "started for R-2" twice.
- The call on [lines 77-83](../src/l6_1_interrupt_and_resume/refunds.py#L77-L83) is where the node stops. `interrupt()` reads the current run's config. If there is no resume value for this interrupt yet, it raises `GraphInterrupt` with an `Interrupt` object that holds the payload dict. LangGraph catches that exception: the node does not fail. The run ends, the checkpoint keeps the task as pending, and `invoke` returns normally.
- On resume, `Command(resume="approved")` puts the value where `interrupt()` looks for it. The same call on line 77 now finds the value and returns it, so `decision` is the plain string `"approved"`.
- The payload on [lines 79-81](../src/l6_1_interrupt_and_resume/refunds.py#L79-L81) is everything the manager needs to decide: the id, the amount and a ready question. It is plain data (strings and an int) because it is saved with the checkpoint and returned to the caller.
- [Line 85](../src/l6_1_interrupt_and_resume/refunds.py#L85) runs only after a resume. [Line 86](../src/l6_1_interrupt_and_resume/refunds.py#L86) stores the human's answer as it is. The node does not check it; 6.2 adds validation.

### [`build_graph`](../src/l6_1_interrupt_and_resume/refunds.py#L93-L107)

- The `checkpointer` parameter on [line 93](../src/l6_1_interrupt_and_resume/refunds.py#L93) is typed `BaseCheckpointSaver | None`, the interface every saver implements. `None` is allowed on purpose: the last test and the first experiment build the graph without a saver.
- [Line 104](../src/l6_1_interrupt_and_resume/refunds.py#L104) adds the conditional edge from `START`. No path map is passed. With no path map, LangGraph builds one from the `Literal` return hint and looks each returned name up in it at run time, so a name outside the `Literal` fails with `KeyError`; the same hint also gives the drawing its two edges (see the comment on refunds.py lines 40-41).
- [Lines 105-106](../src/l6_1_interrupt_and_resume/refunds.py#L105-L106): both nodes end the run. Nothing comes after `manager_review` yet.
- [Line 107](../src/l6_1_interrupt_and_resume/refunds.py#L107) passes the checkpointer to `compile`. With a saver, every step is written under the run's `thread_id`, and so is the pending interrupt. Without one, the pause is still reported to the caller, but nothing is saved. Then `get_state` raises `ValueError: No checkpointer set`, and a resume raises `RuntimeError: Cannot use Command(resume=...) without checkpointer`.

## [\_\_main\_\_.py](../src/l6_1_interrupt_and_resume/__main__.py)

The live run. Each region prints one section of the output.

- [`config`](../src/l6_1_interrupt_and_resume/__main__.py#L9-L16) gives each refund its own thread, `refund-R-2` and so on. Once the graph has a checkpointer, every invoke needs a `thread_id`. Without one LangGraph raises `ValueError` (the last test checks this).
- [Line 23](../src/l6_1_interrupt_and_resume/__main__.py#L23) creates one `InMemorySaver` for the whole run. All three threads live in it, and they are lost when the process exits.

### R-1: no pause ([lines 25-31](../src/l6_1_interrupt_and_resume/__main__.py#L25-L31))

The \$40 request takes the `auto_approve` branch. The check on [line 29](../src/l6_1_interrupt_and_resume/__main__.py#L29) prints `False`: `__interrupt__` appears in a v1 result only when the run paused.

### R-2: the pause ([lines 33-47](../src/l6_1_interrupt_and_resume/__main__.py#L33-L47))

- The invoke on [line 39](../src/l6_1_interrupt_and_resume/__main__.py#L39) returns as usual. Its result is the state so far plus the extra key `__interrupt__`. The key list printed on [line 40](../src/l6_1_interrupt_and_resume/__main__.py#L40) shows it, and shows that `status` is missing.
- [Line 41](../src/l6_1_interrupt_and_resume/__main__.py#L41): in `invoke` the value is a list of `Interrupt` objects. Here it has one item, because only one node paused.
- [Line 43](../src/l6_1_interrupt_and_resume/__main__.py#L43) prints `.value`, which is exactly the dict passed to `interrupt()`.
- [Line 45](../src/l6_1_interrupt_and_resume/__main__.py#L45) prints only whether `.id` is set. The id is generated from the task's namespace, so it is the same every time you read this interrupt, but it is long and not useful to print. 6.3 uses it to address a specific interrupt.

### get_state while paused ([lines 49-68](../src/l6_1_interrupt_and_resume/__main__.py#L49-L68))

- [Line 56](../src/l6_1_interrupt_and_resume/__main__.py#L56) loads the latest checkpoint of `refund-R-2`. It does not need the earlier `result`, only the thread_id.
- `snap.next` on [line 57](../src/l6_1_interrupt_and_resume/__main__.py#L57) is `('manager_review',)`: the node did not finish, so it is still the next one to run.
- `snap.values` on [line 58](../src/l6_1_interrupt_and_resume/__main__.py#L58) has no `__interrupt__` key. In a snapshot the interrupts live in their own fields: `snap.interrupts` ([line 60](../src/l6_1_interrupt_and_resume/__main__.py#L60)) for the whole thread, and `task.interrupts` ([line 64](../src/l6_1_interrupt_and_resume/__main__.py#L64)) per pending task.
- [Line 65](../src/l6_1_interrupt_and_resume/__main__.py#L65) compares the three ids and prints `True`. The invoke result and the snapshot describe the same saved interrupt.

### Resume R-2 ([lines 70-81](../src/l6_1_interrupt_and_resume/__main__.py#L70-L81))

- [Line 76](../src/l6_1_interrupt_and_resume/__main__.py#L76) passes a `Command` instead of an input dict. LangGraph loads the paused checkpoint of `refund-R-2`, runs the pending `manager_review` task again, and hands it the resume value. `route_by_amount` does not run again: the run continues where it stopped.
- The thread_id alone decides which paused run gets the answer. A resume sent to a finished thread (say `refund-R-1`) runs nothing and returns that thread's final state, without an error. The second experiment shows this.
- [Lines 78-79](../src/l6_1_interrupt_and_resume/__main__.py#L78-L79): after the resume, `next` is `()` and there are no interrupts left. The thread is finished.

### R-3: the v2 format ([lines 83-95](../src/l6_1_interrupt_and_resume/__main__.py#L83-L95))

- `version="v2"` on [line 90](../src/l6_1_interrupt_and_resume/__main__.py#L90) changes only what `invoke` returns, not how the graph runs. The result is a `GraphOutput`: `.value` is the clean state and `.interrupts` holds the pending interrupts, as a tuple.
- [Line 93](../src/l6_1_interrupt_and_resume/__main__.py#L93) resumes the same way as in v1. The printed `interrupts=0` means the run finished. Check `len(out.interrupts)` to tell a pause from a finished run, instead of looking for a key.

## [test_interrupt.py](../tests/test_interrupt.py)

The tests check the same behaviour without relying on the printed text. Each test builds its own graph and saver, so the threads never mix.

- [`test_large_refund_pauses`](../tests/test_interrupt.py#L36-L51) compares the three interrupt ids with each other on [line 51](../tests/test_interrupt.py#L51). It never compares them to a fixed string, because the id is generated.
- [`test_resume_uses_the_human_value`](../tests/test_interrupt.py#L54-L69) uses pytest's `capsys` to count the prints: "started" twice, "resumed" once ([lines 68-69](../tests/test_interrupt.py#L68-L69)). That is the restart from the top of the node.
- [`test_v2_output_format`](../tests/test_interrupt.py#L72-L87) turns every `DeprecationWarning` into an error ([line 76](../tests/test_interrupt.py#L76)). This proves that `.value` and `.interrupts` are not the deprecated dict-style access.
- [`test_resume_needs_a_checkpointer`](../tests/test_interrupt.py#L90-L100) shows both sides. Without a saver the pause is reported, but the resume fails ([lines 92-96](../tests/test_interrupt.py#L92-L96)). With a saver, an invoke without a `thread_id` fails ([lines 98-100](../tests/test_interrupt.py#L98-L100)).

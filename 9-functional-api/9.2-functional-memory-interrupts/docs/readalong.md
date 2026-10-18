# 9.2 Functional API: Memory, Interrupts and Determinism — code walkthrough

The order workflow from 9.1 now runs on one "desk" thread. Orders on hold pause for a manager's answer through `interrupt()`, and the thread keeps a tally of all orders it has seen in `previous`. The program reviews Ada's, Bob's and Cleo's orders one after the other and then shows what the thread keeps. Run it with `./run.sh 9.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 9.1

- [`TASK_RUNS` and `OUTBOX`](../src/l9_2_functional_memory_interrupts/workflow.py#L23-L30): a new region that records how often each task's code really ran and which customer messages were "sent".
- [`DeskTally`](../src/l9_2_functional_memory_interrupts/workflow.py#L62-L67) is new. [`OrderOutcome`](../src/l9_2_functional_memory_interrupts/workflow.py#L52-L59) has the same fields, but its final decision is now "approved" or "rejected".
- The four 9.1 tasks each got one first line that counts the run ([lines 79](../src/l9_2_functional_memory_interrupts/workflow.py#L79), [90](../src/l9_2_functional_memory_interrupts/workflow.py#L90), [103](../src/l9_2_functional_memory_interrupts/workflow.py#L103), [110](../src/l9_2_functional_memory_interrupts/workflow.py#L110)). Their logic is unchanged, and so is `decide`.
- [`notify_customer`](../src/l9_2_functional_memory_interrupts/workflow.py#L123-L129) is a new task.
- [`process_order`](../src/l9_2_functional_memory_interrupts/workflow.py#L168-L215) takes a keyword-only `previous`, pauses with `interrupt()` for orders on hold and returns `entrypoint.final(value=..., save=...)`.
- In `__main__.py`, one thread [`DESK`](../src/l9_2_functional_memory_interrupts/__main__.py#L37) replaces 9.1's `config_for`, and [`review`](../src/l9_2_functional_memory_interrupts/__main__.py#L43-L60) plus the `desk_memory` region replace `show` and the three 9.1 sections.
- The tests are rewritten for the new behaviour.

## [workflow.py](../src/l9_2_functional_memory_interrupts/workflow.py)

The whole workflow, as in 9.1. Read it from top to bottom; the parts that did not change are explained in the [9.1 walkthrough](../../9.1-entrypoint-and-task/docs/readalong.md).

### The run log

- [`TASK_RUNS`](../src/l9_2_functional_memory_interrupts/workflow.py#L26) is a `Counter`, so `TASK_RUNS["check_stock"] += 1` works for a name it has not seen yet. It counts real executions of a task's code, not task calls. That difference is the point of the lesson: on resume the body calls the tasks again, but the counter does not move.
- [`OUTBOX`](../src/l9_2_functional_memory_interrupts/workflow.py#L29) stands in for an email service. Both are module-level, so they are shared by every run in the process and are not part of any checkpoint. `__main__.py` clears `TASK_RUNS` per order but never clears `OUTBOX`, so the outbox at the end lists every message of the whole run.

### The types

- [`OrderOutcome`](../src/l9_2_functional_memory_interrupts/workflow.py#L52-L59): `decide` still returns "on_hold", but `process_order` replaces it with the manager's answer before it returns, so the caller only ever sees "approved" or "rejected" (line 57 says so).
- [`DeskTally`](../src/l9_2_functional_memory_interrupts/workflow.py#L62-L67) is the type of what the thread remembers between runs. It is separate from `OrderOutcome`: the caller gets one order's result, while the next run gets a running count over all orders.

### The tasks

- The four check tasks are the 9.1 tasks plus the counter line. Because the counter is the first line of each body, it counts every time LangGraph actually executes the task, and only then.
- [`notify_customer`](../src/l9_2_functional_memory_interrupts/workflow.py#L123-L129) is the side effect of this lesson. As a task, its return value (the note on line 127) is saved in the checkpoint like every task result. When the body runs again after a resume, the call on line 188 gets that saved note back, and line 128 does not run a second time. The live run shows this: Bob's body starts twice, but `task runs` shows `'notify_customer': 1`, and the outbox holds one note per paused order.

### The entrypoint

- [`process_order`](../src/l9_2_functional_memory_interrupts/workflow.py#L168-L215), signature on lines 169–171:
  - `previous` is recognised by its name. It is keyword-only here (after the `*`), the form most docs examples use; an ordinary parameter named `previous` would be filled in too. LangGraph fills it in; the caller never passes it. On a new thread it is `None`, which is why the default and the `| None` are there.
  - The return annotation `entrypoint.final[OrderOutcome, DeskTally]` names two types: what the caller gets and what is saved for `previous`. LangGraph uses the first one as the output schema. Both type arguments are required.
- Line 175 prints on every execution of the body. It is a side effect left in the body on purpose: in the live run it appears twice for Bob and twice for Cleo, once before the pause and once after the resume, both times with the same `previous`. `previous` only changes when a run finishes, and a paused run has not finished.
- Lines 179–186 are the 9.1 body, except that the outcome is kept in a variable instead of being returned at once.
- Line 188 calls `notify_customer` and waits for it with `.result()`. Only orders on hold get here, which is why Ada's `task runs` line has no `notify_customer`.
- [Lines 197–203](../src/l9_2_functional_memory_interrupts/workflow.py#L197-L203): `interrupt()` is the same function as in 6.1. On the first pass it stops the body and LangGraph saves the run as paused; the dict becomes the payload the caller reads from `out.interrupts`. On the resumed pass, the body gets here again, and this time `interrupt()` returns the value from `Command(resume=...)` instead of stopping. Lines 204–205 then run for the first time.
- The comment on lines 189–196 is the determinism rule. On resume the body replays from line 175, and each task call is matched with its saved result. Code in the body runs again for real, so it must take the same path as before the pause. A `random` or time call in the body would give a different value on the second pass; inside a task its saved result would be reused.
- Line 205 maps any answer other than "approve" to "rejected".
- [Lines 206–211](../src/l9_2_functional_memory_interrupts/workflow.py#L206-L211) update the tally. `previous or {...}` starts a fresh count when `previous` is `None`. The dict is copied with `**tally`, not changed in place, and `outcome["decision"]` is used as the key, which works because the decision is "approved" or "rejected" by now.
- Line 215 splits the result: `value` goes to the caller and to `get_state().values`, `save` goes to the checkpoint and comes back as `previous` on the next run of this thread. With a plain `return outcome`, both would be the outcome, and line 209 of the next run would fail, because an outcome has no `"orders"` key.

## [\_\_main\_\_.py](../src/l9_2_functional_memory_interrupts/__main__.py)

The entry point. `ADA`, `BOB` and `CLEO` are the same three orders as in 9.1: Ada passes every check, Bob fails all three, Cleo fails only the address.

- [`DESK`](../src/l9_2_functional_memory_interrupts/__main__.py#L37) is one thread for all three orders. `previous` belongs to a thread, so only orders that share a thread share a tally. With 9.1's one thread per order, every run would start with `previous=None`.
- [`ANSWERS`](../src/l9_2_functional_memory_interrupts/__main__.py#L39) stands in for the manager, so every run prints the same output.

### review

[`review`](../src/l9_2_functional_memory_interrupts/__main__.py#L43-L60) handles one order.

- Line 46 clears the task counter, so each `task runs` line counts one order, including its resume.
- Line 51 passes `version="v2"`, as in 6.1, so `invoke` returns an object with `.value` and `.interrupts` instead of a plain dict.
- Line 52 decides whether the run paused by looking at `out.interrupts`. The value is not useful here: while Bob's run is paused, `out.value` is still Ada's outcome, the last finished run on the thread.
- Line 53 prints the payload from line 197 of `workflow.py`, `out.interrupts[0].value`. This lesson raises at most one interrupt per run, so index 0 is enough.
- Line 58 resumes. It sends `Command(resume=answer)` instead of an order, on the same `DESK` config. LangGraph finds the paused run on that thread, restores its input and runs the body again, so `order` inside the body is still Bob's order.
- Lines 59–60 print the final decision and the counter. After the resume, every task shows 1, although the body called each of them twice.

### main

[`main`](../src/l9_2_functional_memory_interrupts/__main__.py#L66-L81) reviews the three orders on `DESK`, then shows what the thread keeps.

- Line 73 prints the outbox: one note for Bob and one for Cleo, none for Ada.
- Line 75 reads `get_state(DESK).values`. It holds Cleo's outcome, the `value` of the last `entrypoint.final`. The tally is not there.
- Lines 79–80 find the tally in the `"__previous__"` channel of the latest checkpoint: `{'orders': 3, 'approved': 2, 'rejected': 1}`. This is an internal channel name, read only to show where `save` goes, like `"__return__"` in 9.1. In your own code, the way to read it is through `previous` in the next run.

## [test_workflow.py](../tests/test_workflow.py)

- [`clean_run_log`](../tests/test_workflow.py#L45-L50) is an autouse fixture, so every test starts with an empty counter and outbox. [`config_for`](../tests/test_workflow.py#L53-L55) gives each test its own thread name, because all tests share the module-level `checkpointer` and a reused thread would carry a tally from another test.
- [`run`](../tests/test_workflow.py#L58-L63) is the same pattern as `review`: invoke, and resume if paused.
- [`test_on_hold_order_pauses_for_manager`](../tests/test_workflow.py#L79-L90) checks the paused state from outside: line 89 shows that `get_state(config).next` still names the `process_order` node, which means the run is waiting.
- [`test_resume_reuses_finished_tasks`](../tests/test_workflow.py#L93-L114) is the determinism check: each task ran once, and the outbox has one note.
- [`test_previous_and_final_split_value_and_save`](../tests/test_workflow.py#L117-L140) checks both halves of `entrypoint.final`: the caller never sees the tally (line 126), and the checkpoint holds it. Lines 137–140 run Ada on a second thread, whose tally starts again from 1.
- [`test_previous_is_injected`](../tests/test_workflow.py#L143-L149) reads the body's print through `capsys`: `previous=None` on the first run of a thread, and the saved tally on the second.

# 6.5 Time Travel: History, Replay and Forks — code walkthrough

The program runs one refund request, R-4 (\$300, the manager approves \$120), and then travels through that thread: it lists the saved checkpoints, replays the run from two past checkpoints, and forks it twice with `update_state`. Run it with `./run.sh 6.5` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 6.2

The graph does not change at all. Time travel is something the caller does with the checkpoints the saver already keeps, so the whole lesson is in the entry point.

- [refunds.py](../src/l6_5_time_travel/refunds.py) is byte-identical to 6.2's. Only the package name around it changed. It is explained in [6.2's read-along](../../6.2-interrupt-patterns/docs/readalong.md).
- [`__main__.py`](../src/l6_5_time_travel/__main__.py) is rewritten. [`config`](../src/l6_5_time_travel/__main__.py#L12-L19) and [`outcome`](../src/l6_5_time_travel/__main__.py#L44-L49) are kept as they were. Two helpers are new: [`at_checkpoint`](../src/l6_5_time_travel/__main__.py#L23-L38) and [`describe`](../src/l6_5_time_travel/__main__.py#L53-L66). 6.2's five requests are replaced by one thread and eight sections that travel through it.
- The tests moved from `test_patterns.py` to [test_time_travel.py](../tests/test_time_travel.py).

## What to keep in mind from refunds.py

Two facts about 6.2's graph decide what happens in the forks below:

- The only edge out of `START` is the conditional edge [`route_by_amount`](../src/l6_5_time_travel/refunds.py#L46-L52) ([line 183](../src/l6_5_time_travel/refunds.py#L183)). Change `amount` "as input" and this function runs again on the new value.
- [`manager_review`](../src/l6_5_time_travel/refunds.py#L97-L146) has no static edge. It picks the next node only through the `goto` of the `Command` it returns. [`auto_approve`](../src/l6_5_time_travel/refunds.py#L59-L64) does have one, to `pay_refund` ([line 184](../src/l6_5_time_travel/refunds.py#L184)).

The prints on [line 108](../src/l6_5_time_travel/refunds.py#L108) and [line 155](../src/l6_5_time_travel/refunds.py#L155) are what show you, in the output, which nodes really ran during a replay.

## [\_\_main\_\_.py](../src/l6_5_time_travel/__main__.py)

### Helpers

- [`at_checkpoint`](../src/l6_5_time_travel/__main__.py#L23-L38) builds the config of one past checkpoint. `thread_id` alone means "the newest checkpoint of the thread". Adding `checkpoint_id` points at one saved checkpoint instead, and every time-travel call in this file takes such a config. The program could pass a snapshot's own `.config` (the tests do), which already holds the same three keys. The helper shows what is inside it.
- `checkpoint_ns` on [line 34](../src/l6_5_time_travel/__main__.py#L34) looks optional, and for `invoke` and `get_state` it is. But `update_state` with `InMemorySaver` (langgraph-checkpoint 4.3.0) needs the key and fails with `KeyError: 'checkpoint_ns'` without it. The empty string is the namespace of the top-level graph. Subgraphs have their own namespaces.
- [`describe`](../src/l6_5_time_travel/__main__.py#L53-L66) turns one `StateSnapshot` into one line. `step` and `source` come from `snap.metadata`, which on 1.2.16 holds exactly `source`, `step` and `parents`. `snap.next` is the tuple of nodes that would run if you continued from this checkpoint. `values.get` is used because early checkpoints don't have the later keys yet. The checkpoint id is never printed: it is generated from the current time, so it would change the output on every run.

### [`main`](../src/l6_5_time_travel/__main__.py#L72-L210)

[Line 76](../src/l6_5_time_travel/__main__.py#L76) builds 6.2's graph with an `InMemorySaver`. The saver is the only thing time travel needs: it keeps every checkpoint of a thread, not just the last one. All the sections below use one thread, `refund-R-4`.

### The original run ([lines 82-88](../src/l6_5_time_travel/__main__.py#L82-L88))

This is 6.2's edit case: the first invoke pauses in `manager_review`, and the resume on [line 86](../src/l6_5_time_travel/__main__.py#L86) approves \$120. That is why `[manager_review] started` prints twice: once for the run that paused and once for the run that resumed.

### History ([lines 92-111](../src/l6_5_time_travel/__main__.py#L92-L111))

- `get_state_history` on [line 97](../src/l6_5_time_travel/__main__.py#L97) yields the same `StateSnapshot` objects as `get_state` (lesson 5.1), one per saved checkpoint, newest first. It is a generator, so `list()` keeps the result for the lookups below.
- The four lines of output are the four checkpoints of one run. Step -1 (source `input`) holds the input before any node ran, so `next` is `('__start__',)`. Step 0 is after `START` routed the request: `next` is `('manager_review',)`. Step 1 is after `manager_review` decided, and step 2 is after `pay_refund`, with nothing left to run.
- The pause has no checkpoint of its own. The run paused while it was at step 0, and the resume continued from that same checkpoint. So "the moment the manager was asked" is step 0.
- [Lines 103-104](../src/l6_5_time_travel/__main__.py#L103-L104) find the two checkpoints by their `next`, not by their index. Once the thread branches, new checkpoints land at the top of the list and the same step numbers appear several times, so an index or a step number no longer identifies a checkpoint.
- [Lines 105-106](../src/l6_5_time_travel/__main__.py#L105-L106) keep only the ids, the way an app would store them (in an audit log, in a URL). `at_checkpoint` turns them back into configs later.

### Replay from step 1 ([lines 115-125](../src/l6_5_time_travel/__main__.py#L115-L125))

- [Line 123](../src/l6_5_time_travel/__main__.py#L123) is a replay: input `None` plus a config with a `checkpoint_id`. `None` means "no new input, continue", and the `checkpoint_id` says from where.
- LangGraph loads that checkpoint and runs what is in its `next`, here `pay_refund`. Nodes that ran before the checkpoint are not run again: their writes are already saved in it. That is why the manager is not asked and `decided_by` and `approved_amount` are still the original ones. The test counts `check_answer` calls to prove that `manager_review` did not run.
- Nodes after the checkpoint really run again. The output shows a second `[pay_refund] paying $120` line: the customer would be paid twice. Replay is not a read from a cache, so any side effect after the chosen checkpoint must be safe to repeat (the idempotency rule from [6.3](../../6.3-rules-of-interrupts/docs/notes.md#idempotent-safe-to-repeat)).
- Replay does not overwrite anything. It first writes a new checkpoint with source `fork` (a copy of the chosen one, one step later, whose parent is the chosen one) and continues from there. You will see it in the history section.
- Observed on 1.2.16, not promised by the docs: replaying the final checkpoint (step 2, `next` empty) runs no node and returns the same values, but it still adds one `fork` checkpoint. One of the experiments in the notes shows it.

### Replay from step 0 ([lines 129-140](../src/l6_5_time_travel/__main__.py#L129-L140))

- [Line 133](../src/l6_5_time_travel/__main__.py#L133) replays the checkpoint where `manager_review` paused. The node runs again from its first line, reaches `interrupt()`, and pauses again. `out.interrupts` holds the same \$300 question as in the original run.
- The \$120 answer from the original run is not reused. So time travel to a pause is a way to ask the human again and give a different answer.
- [Line 138](../src/l6_5_time_travel/__main__.py#L138) resumes with the plain `thread` config. After the replay, its `fork` checkpoint is the newest one in the thread, and the new pause is recorded there, so a resume on the thread finds it. The answer is `reject`, so `reject_refund` runs.
- Why not resume through `at_checkpoint(paused_id)`? On 1.2.16 that resume ignores the new answer and applies the answer saved at that checkpoint again (approve \$120). This is observed behaviour, not a documented contract. The rule to follow: after a replay or a fork, resume on the thread.

### The kept history ([lines 144-154](../src/l6_5_time_travel/__main__.py#L144-L154))

- The output now has nine lines. Read them from the bottom: the four original checkpoints, then the step 1 replay (`fork` at step 2, then step 3), then the step 0 replay (`fork` at step 1, `reject_refund` pending at step 2, the end at step 3). Nothing was deleted, and the approved run is still there.
- The list is ordered by time across all branches, which is why step 3 and step 2 appear twice. Each snapshot's `parent_config` is what links a branch together.
- `get_state(thread)` on [line 152](../src/l6_5_time_travel/__main__.py#L152) reads only the newest checkpoint, here the rejected end. That is the "current" state of the thread, the one a plain resume or a plain invoke continues from.

### Fork with update_state ([lines 158-178](../src/l6_5_time_travel/__main__.py#L158-L178))

- [Line 162](../src/l6_5_time_travel/__main__.py#L162): `update_state` takes the config of a past checkpoint and the values to change. It does not edit that checkpoint. It writes a new one with source `update`, one step later, whose parent is the given checkpoint, and returns the new checkpoint's config. That config is also the newest in the thread.
- The values are applied as if a node had returned them, through that node's writers and the state's reducers. `RefundState` has no reducers, so `amount` is simply replaced with 250. Which node? Without `as_node`, LangGraph picks the node that wrote last before the chosen checkpoint. Before step 0 that is the input, `__start__`.
- That choice decides what runs next. Writing "as `__start__`" means `START`'s conditional edge runs again, so `route_by_amount` sees \$250, which is above the limit, and `next` is `('manager_review',)`. That is what the `describe` line shows. With \$90 the same edge would pick `auto_approve` (the test checks this).
- [Lines 165-168](../src/l6_5_time_travel/__main__.py#L165-L168) confirm the parent link by comparing ids, without printing them.
- [Line 174](../src/l6_5_time_travel/__main__.py#L174) continues from the fork with `invoke(None, fork)`. `manager_review` asks again, now about \$250: interrupts fire in a fork just as in a replay. [Line 176](../src/l6_5_time_travel/__main__.py#L176) resumes it on the thread like any other pause, and \$250 is paid.

### Fork with as_node ([lines 182-196](../src/l6_5_time_travel/__main__.py#L182-L196))

- `as_node` names the node the update pretends to come from. The graph then continues along that node's edges.
- The loop on [lines 190-192](../src/l6_5_time_travel/__main__.py#L190-L192) writes the same values from step 0 twice, so it creates two forks. As `manager_review`, `next` is `()`. The node's real routing lives in the `goto` of the `Command` it returns at run time. A plain dict has no `goto`, and the node has no static edge, so nothing follows. That branch ends right away, and nothing is paid.
- As `auto_approve`, `next` is `('pay_refund',)` because of the static edge `auto_approve -> pay_refund`. The values look like the policy's decision, and `manager_review`, with its interrupt, is skipped.
- After the loop `fork` holds the last one, the `auto_approve` fork. [Line 194](../src/l6_5_time_travel/__main__.py#L194) continues it, and only `pay_refund` runs, paying \$300 by policy.
- A name that is not a node (`as_node="nope"`) raises `InvalidUpdateError`. The last test checks this.

### Every branch ([lines 200-209](../src/l6_5_time_travel/__main__.py#L200-L209))

- A snapshot with an empty `next` is the end of a branch. [Lines 205-207](../src/l6_5_time_travel/__main__.py#L205-L207) collect those ends.
- 15 checkpoints: 4 from the original run, 2 from the first replay, 3 from the second, 3 from the \$250 fork (update, after `manager_review`, after `pay_refund`) and 3 from the `as_node` forks (two updates and the payment).
- The six ends, newest first: the `auto_approve` fork, the `manager_review` fork that never paid (status `None`), the \$250 fork, the rejected replay, the step 1 replay and the original run. One request, one thread, and every attempt is still there to inspect.

## [test_time_travel.py](../tests/test_time_travel.py)

The tests check the same behaviour through snapshots instead of printed lines. They use each snapshot's own `.config` instead of `at_checkpoint`, and they never compare an id with a fixed value, only ids with each other.

- [`original_run`](../tests/test_time_travel.py#L28-L36) is the shared setup: a fresh graph and saver, the \$120 approval, the history, and the two picked snapshots. Each test starts from a clean thread.
- [`test_history_of_the_original_run`](../tests/test_time_travel.py#L39-L71) checks the four `(step, source, next)` triples, and that `before_pay` already has `approved_amount` but no `status`. [Lines 55-57](../tests/test_time_travel.py#L55-L57) follow the `parent_config` chain down to the input checkpoint, which has no parent. [Lines 61-71](../tests/test_time_travel.py#L61-L71) show that `get_state` with a past `checkpoint_id` returns that past snapshot.
- [`test_replay_after_decision_reruns_only_what_follows`](../tests/test_time_travel.py#L74-L101) wraps `check_answer` in a counter ([lines 81-88](../tests/test_time_travel.py#L81-L88)), as 6.2 did. This works because `manager_review` looks the name up in the module each time it runs. Zero calls and exactly one `[pay_refund]` line ([lines 92-93](../tests/test_time_travel.py#L92-L93)) prove that only the node after the checkpoint ran. [Lines 97-101](../tests/test_time_travel.py#L97-L101) check the new `fork` checkpoint and its parent.
- [`test_replay_before_decision_asks_again`](../tests/test_time_travel.py#L104-L126) checks that the replay pauses with the \$300 question and that the head of the thread is now the `fork` checkpoint ([lines 115-119](../tests/test_time_travel.py#L115-L119)). After the reject, [line 125](../tests/test_time_travel.py#L125) shows both ends, rejected and approved, in the history.
- [`test_fork_without_as_node`](../tests/test_time_travel.py#L129-L152) checks the `update` checkpoint: source, step, `next`, parent and values ([lines 133-138](../tests/test_time_travel.py#L133-L138)). It then pays \$250 and checks that the \$120 branch is untouched. [Lines 151-152](../tests/test_time_travel.py#L151-L152) show that \$90 sends the fork to `auto_approve`.
- [`test_as_node_picks_the_next_node`](../tests/test_time_travel.py#L155-L184) checks the dead end as `manager_review` and the path as `auto_approve`, and compares the whole final state on [lines 171-177](../tests/test_time_travel.py#L171-L177). `review_error` is missing because `manager_review` never ran on that branch. [Lines 183-184](../tests/test_time_travel.py#L183-L184) show the trap of inference: from step 1 LangGraph infers `manager_review` as the writer, so the fork has nothing to run, and nothing is paid.

# 6.3 The Rules of Interrupts — code walkthrough

The program runs two graphs. The refund graph from 6.2 shows that a resumed node starts again from its first line, so the manager notification before `interrupt()` runs twice and must be safe to repeat. A new sign-off graph asks a manager and finance in parallel, so two interrupts are pending at once and are resumed by `Interrupt.id`. The manager answers two questions in one node, matched by order. Run it with `./run.sh 6.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 6.2

The refund graph is 6.2's "refund-approval" example with one small addition. The parts that did not change (`RefundState`, `route_by_amount`, `check_answer`, the `Command` routing in `manager_review`, the outcome nodes and `build_graph`) are explained in [6.2's read-along](../../6.2-interrupt-patterns/docs/readalong.md).

- [`notify_manager`](../src/l6_3_rules_of_interrupts/refunds.py#L84-L96) is new, together with two module-level records: [`NOTIFY_CALLS`](../src/l6_3_rules_of_interrupts/refunds.py#L74) and [`MANAGER_INBOX`](../src/l6_3_rules_of_interrupts/refunds.py#L80).
- [`manager_review`](../src/l6_3_rules_of_interrupts/refunds.py#L129-L182) has one new line, [line 144](../src/l6_3_rules_of_interrupts/refunds.py#L144), which calls `notify_manager` before `interrupt()`. Nothing else in it changed.
- [signoff.py](../src/l6_3_rules_of_interrupts/signoff.py) is a new, separate graph: two parallel sign-off nodes and a join node.
- [`__main__.py`](../src/l6_3_rules_of_interrupts/__main__.py) is rewritten: 6.2's `outcome` helper and its five sections are gone. Two new helpers, `show_pending` and `show_runs`, and four new sections replace them.
- The tests moved to [test_rules.py](../tests/test_rules.py), and 6.2's tests were dropped.

## [refunds.py](../src/l6_3_rules_of_interrupts/refunds.py)

The refund graph from 6.2, which now notifies the manager before it pauses. This file shows the first rule: code before `interrupt()` runs again on every resume.

- [Line 11](../src/l6_3_rules_of_interrupts/refunds.py#L11) imports `Counter` for the call counter.

### [`notify_manager`](../src/l6_3_rules_of_interrupts/refunds.py#L73-L99)

A stand-in for sending an email or opening a ticket: a side effect that the manager would notice if it happened twice.

- [`NOTIFY_CALLS`](../src/l6_3_rules_of_interrupts/refunds.py#L74) and [`MANAGER_INBOX`](../src/l6_3_rules_of_interrupts/refunds.py#L80) are plain module globals, not graph state. LangGraph does not save them in the checkpoint and does not reset them, so they keep counting across every invoke in the same process, just as a real mail server would. That is why the tests clear them before each test.
- [Line 89](../src/l6_3_rules_of_interrupts/refunds.py#L89) counts *calls*, before the check. So `NOTIFY_CALLS` shows how often the code before `interrupt()` ran, and `MANAGER_INBOX` shows what was actually sent. The gap between the two numbers is the point of the lesson.
- [Lines 95-96](../src/l6_3_rules_of_interrupts/refunds.py#L95-L96) make the call idempotent: the message text itself works as the key, so a second call for the same request and amount sends nothing. In a real system the "have I sent this already?" check would be an idempotency key or an upsert in the external system, not a Python list.

### [`manager_review`](../src/l6_3_rules_of_interrupts/refunds.py#L129-L182)

- [Line 144](../src/l6_3_rules_of_interrupts/refunds.py#L144) is the only change. It sits between the "started" print on [line 140](../src/l6_3_rules_of_interrupts/refunds.py#L140) and `interrupt()` on [line 154](../src/l6_3_rules_of_interrupts/refunds.py#L154). On the first run the node reaches `interrupt()` and pauses. On the resume LangGraph does not continue from line 154: it calls `manager_review` again from the top, and only this time `interrupt()` returns the answer. So line 144 runs once per run of the node, and the "started" print shows each of those runs.
- In the validation loop it runs even more often. A bad answer sends the graph back into `manager_review` through `goto` on [line 164](../src/l6_3_rules_of_interrupts/refunds.py#L164), which starts yet another run. Each bad answer therefore costs two more calls: one for the resumed run that checks the answer, one for the new run that asks again (the second test counts them).
- The comment above line 144 names the two alternatives: put the side effect after `interrupt()`, where it runs only once the answer has arrived, or move it into its own node before `manager_review`, which LangGraph runs once and does not run again on a resume.

## [signoff.py](../src/l6_3_rules_of_interrupts/signoff.py)

A second, small graph for refunds above \$1000: a manager and finance must both approve. It shows the order rule (several interrupts in one node are matched by order) and the try/except rule, and, from the guide's separate "Handling multiple interrupts" section, how parallel interrupts are resumed by id. As the [module docstring](../src/l6_3_rules_of_interrupts/signoff.py#L9-L13) says, it does not replace `refunds.py`, whose `manager_review` keeps one `interrupt()` per run.

### [`signoff_state`](../src/l6_3_rules_of_interrupts/signoff.py#L24-L48)

- [`NODE_RUNS`](../src/l6_3_rules_of_interrupts/signoff.py#L25) counts how often each sign-off node starts. It replaces the "started" prints of `refunds.py`. The two sign-offs run in the same step, and the order in which LangGraph starts parallel nodes is not fixed, so prints from them could swap places between runs. Counts give the same output every time.
- [`SignoffState`](../src/l6_3_rules_of_interrupts/signoff.py#L33-L45) has no reducers. That is safe because each parallel node writes its own keys: `manager_signoff` writes `manager_decision` and `manager_reason`, `finance_signoff` writes `finance_decision`. If both wrote the same key in the same step, the `LastValue` channel would raise `InvalidUpdateError`, as in lesson 3.1.

### [`manager_signoff`](../src/l6_3_rules_of_interrupts/signoff.py#L52-L79)

Two `interrupt()` calls in one node: the decision on [lines 67-72](../src/l6_3_rules_of_interrupts/signoff.py#L67-L72), then the reason on [lines 73-78](../src/l6_3_rules_of_interrupts/signoff.py#L73-L78).

- What happens at run time: `interrupt()` asks the task's scratchpad for a counter, so the first call in a run gets index 0 and the second gets index 1. LangGraph keeps the answers this task has received in a list. A call whose index is in that list returns the stored answer. Otherwise it takes a new resume value if one was sent, and otherwise it raises `GraphInterrupt` to pause (this is `interrupt()` in `langgraph/types.py`). So the node runs three times in the lesson. Run 1 pauses at the decision. Before run 2, the resume map adds the decision to this task's stored answers, so run 2 gets it at index 0 as a stored answer and pauses at the reason. Run 3 replays the stored decision at index 0 and gets the reason at index 1.
- Nothing ties an answer to a question except its index. That is why the order must never change between runs, and why neither call may be skipped by an `if`. If the reason were asked first after a redeploy, the stored "approve" would come back as the reason (one of the experiments in the notes shows this).
- Both pauses of this node have the same `Interrupt.id`. `Interrupt.from_ns` builds the id as a hash of the task's checkpoint namespace, which names the node's task, not the question. The id tells LangGraph *which task* an answer is for. The index then picks *which call* inside that task.
- [Line 76](../src/l6_3_rules_of_interrupts/signoff.py#L76) puts the first answer into the second question. This works because the decision is a replayed value on every later run, so the text of the second question is the same each time.
- The comment on [lines 63-65](../src/l6_3_rules_of_interrupts/signoff.py#L63-L65) is the try/except rule. `GraphInterrupt` subclasses `GraphBubbleUp`, which subclasses `Exception` (`langgraph/errors.py`). An `except Exception` around either call would catch the pause, and the node would finish without asking. The code has no such block. The notes have an experiment that adds one.
- The `"role"` key in both payloads is for the caller. With two interrupts pending, it is the only way `__main__.py` can tell which one is the manager's.

### [`finance_signoff`](../src/l6_3_rules_of_interrupts/signoff.py#L86-L90)

One question, on [line 89](../src/l6_3_rules_of_interrupts/signoff.py#L89). It runs in the same step as `manager_signoff`, so after the first invoke both are paused at the same time.

### [`settle`](../src/l6_3_rules_of_interrupts/signoff.py#L97-L106)

The join. [Line 103](../src/l6_3_rules_of_interrupts/signoff.py#L103) needs both decisions, so a single "reject" rejects the refund (the last test checks this). `settle` can read both keys without `.get`, because the waiting edge only starts it once both sign-offs have written theirs. It is the only node that prints: it runs alone in its step, so its line always lands in the same place.

### [`build_signoff_graph`](../src/l6_3_rules_of_interrupts/signoff.py#L113-L129)

The wiring from lesson 3.1.

- [Lines 124-125](../src/l6_3_rules_of_interrupts/signoff.py#L124-L125): two edges from `START` put both sign-offs into the first step.
- [Line 127](../src/l6_3_rules_of_interrupts/signoff.py#L127) is the waiting edge. A list of sources means `settle` waits until *both* sign-offs have finished, and then runs once. While the manager is still paused, `settle` does not start.
- [Line 129](../src/l6_3_rules_of_interrupts/signoff.py#L129) compiles with the checkpointer. As in `refunds.py`, the pause is a saved checkpoint, so without one nothing could be resumed.

## [\_\_main\_\_.py](../src/l6_3_rules_of_interrupts/__main__.py)

The live run. Each region prints one section of the output. Every invoke passes `version="v2"`, so the state is in `out.value` and the pending interrupts are in `out.interrupts` (from 6.1). The program never prints interrupt ids, which change from run to run. It prints counts and comparisons instead.

- [`config`](../src/l6_3_rules_of_interrupts/__main__.py#L14-L21) is unchanged from 6.2: one thread per request.
- [`show_pending`](../src/l6_3_rules_of_interrupts/__main__.py#L24-L31) prints who is asked what. The order of `out.interrupts` for parallel nodes is not stable in 1.2.16, so [line 30](../src/l6_3_rules_of_interrupts/__main__.py#L30) sorts by role before printing. The rest of the program also picks interrupts by role, never by position.
- [`show_runs`](../src/l6_3_rules_of_interrupts/__main__.py#L34-L39) prints the `NODE_RUNS` counts, the evidence for which sign-off node ran again.

### R-2: the node restarts ([lines 47-59](../src/l6_3_rules_of_interrupts/__main__.py#L47-L59))

- [Line 50](../src/l6_3_rules_of_interrupts/__main__.py#L50) pauses the \$250 refund in `manager_review`, and [line 51](../src/l6_3_rules_of_interrupts/__main__.py#L51) resumes it with an approval. The output shows two "started" lines, one per run of the node.
- [Lines 56-57](../src/l6_3_rules_of_interrupts/__main__.py#L56-L57) print the result: `notify_manager` was called 2 times, but the inbox holds one message.

### R-6: the parallel pause ([lines 61-74](../src/l6_3_rules_of_interrupts/__main__.py#L61-L74))

- [Line 64](../src/l6_3_rules_of_interrupts/__main__.py#L64) starts the \$1500 refund. Both sign-offs pause in step 1, so `show_pending` reports 2 interrupts and each node has run once.
- [Line 70](../src/l6_3_rules_of_interrupts/__main__.py#L70) tries a plain resume value. LangGraph checks the resume before any node runs: a dict counts as an id map only if every key is a 32-character hex id. Anything else is refused with `RuntimeError` when more than one interrupt is pending (in `pregel/_loop.py`). No node runs, the counts stay at 1 and 1, and the thread is still paused.
- [Line 72](../src/l6_3_rules_of_interrupts/__main__.py#L72) cuts the message at `" Docs:"` so the printed line drops the documentation link.

### R-6: resume by id ([lines 76-96](../src/l6_3_rules_of_interrupts/__main__.py#L76-L96))

- [Line 79](../src/l6_3_rules_of_interrupts/__main__.py#L79) saves each role's id, to compare later.
- [Line 84](../src/l6_3_rules_of_interrupts/__main__.py#L84) builds the id map: each key is the id of a pending interrupt, and each value is the answer for the role in its payload. LangGraph hands each value to the task whose interrupt has that id.
- `finance_signoff` runs again, gets its answer and finishes. `manager_signoff` runs again: its first `interrupt()` takes "approve" and its second one pauses. So there is again one pending interrupt, and both counts are 2.
- [Line 92](../src/l6_3_rules_of_interrupts/__main__.py#L92) can use `out.interrupts[0]` because only one is pending now. It prints `True`: the new pause has the same id as the manager's first question, because both belong to the same task.

### R-6: the second question ([lines 98-109](../src/l6_3_rules_of_interrupts/__main__.py#L98-L109))

- [Line 105](../src/l6_3_rules_of_interrupts/__main__.py#L105) resumes with a plain value, which is allowed again because only one interrupt is pending.
- Only `manager_signoff` runs again (count 3). `finance_signoff`'s result from the previous resume is saved in the checkpoint, so LangGraph does not run it again, and its count stays at 2. The manager's first `interrupt()` replays "approve", and the second returns "duplicate charge".
- Then `settle` runs, and its line appears *before* "pending interrupts: 0", because it prints during the invoke.

## [test_rules.py](../tests/test_rules.py)

The tests check the same behaviour with counts, sets and id comparisons. They never assume an order of interrupts or of parallel nodes, and they never check an id's value.

- [`clear_module_state`](../tests/test_rules.py#L18-L24) is an autouse fixture. The counters and the inbox are module globals that survive between tests, so without it one test's calls would add to the next test's counts.
- [`test_restart_runs_notification_twice_but_sends_once`](../tests/test_rules.py#L27-L39) checks the R-2 section: two "started" lines, 2 calls, 1 message.
- [`test_reask_loop_reruns_code_before_interrupt`](../tests/test_rules.py#L42-L54) expects 4 calls on [line 51](../tests/test_rules.py#L51): the first run, then two for the bad answer `"yes"` (the run that checks it and the new run that asks again), then one for the good answer. There is still one message.
- [`test_parallel_pause_refuses_plain_resume`](../tests/test_rules.py#L57-L72) compares roles and `next` as sets. [Line 64](../tests/test_rules.py#L64) unpacks the two interrupts only to check that the ids differ, which does not depend on their order. [Lines 71-72](../tests/test_rules.py#L71-L72) show that the refused resume changed nothing.
- [`test_id_map_then_second_question_in_order`](../tests/test_rules.py#L75-L103) follows the R-6 sections. [Line 93](../tests/test_rules.py#L93) checks that `manager_decision` is not in the state after the id-map resume: the manager node has not finished, so it has written nothing yet, while finance's answer is already there ([line 92](../tests/test_rules.py#L92)).
- [`test_both_signoffs_must_approve`](../tests/test_rules.py#L106-L119) runs the same flow with a finance reject and checks that `settle` rejects the refund.

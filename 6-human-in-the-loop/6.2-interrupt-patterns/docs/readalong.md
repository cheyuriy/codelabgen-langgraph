# 6.2 Approve, Edit and Validate: Interrupt Patterns — code walkthrough

The program sends five refund requests through the refund graph from 6.1. A \$40 refund is paid by policy. The four larger ones pause for a manager, and the manager's answer decides what happens next: approve, reject, approve a lower amount, or send something invalid and get asked again. Run it with `./run.sh 6.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 6.1

The example is 6.1's "refund-approval" graph. The parts that did not change (`REFUND_LIMIT`, `route_by_amount`, the checkpointer parameter, `config`) are explained in [6.1's read-along](../../6.1-interrupt-and-resume/docs/readalong.md).

- [`RefundState`](../src/l6_2_interrupt_patterns/refunds.py#L21-L39) has two new keys: `approved_amount` ([line 36](../src/l6_2_interrupt_patterns/refunds.py#L36)) and `review_error` ([line 39](../src/l6_2_interrupt_patterns/refunds.py#L39)).
- [`auto_approve`](../src/l6_2_interrupt_patterns/refunds.py#L59-L64) no longer sets `status`. It sets `approved_amount` and hands over to `pay_refund`.
- [`check_answer`](../src/l6_2_interrupt_patterns/refunds.py#L71-L86) is new: a plain function that checks the manager's answer.
- [`manager_review`](../src/l6_2_interrupt_patterns/refunds.py#L97-L146) returns a `Command` that picks the next node, instead of a dict. On an invalid answer it sends the graph back into itself to ask again.
- [`pay_refund` and `reject_refund`](../src/l6_2_interrupt_patterns/refunds.py#L153-L162) are new nodes. They write the final `status`.
- [`build_graph`](../src/l6_2_interrupt_patterns/refunds.py#L169-L187) adds the two nodes and drops 6.1's `manager_review -> END` edge.
- [`__main__.py`](../src/l6_2_interrupt_patterns/__main__.py) is rewritten: a new `outcome` helper, five sections, and `version="v2"` on every invoke.
- The tests moved to [test_patterns.py](../tests/test_patterns.py).

## [refunds.py](../src/l6_2_interrupt_patterns/refunds.py)

The state, the routing function, four nodes, the answer check and `build_graph`. Every node is plain Python, so the run is offline and the output is always the same.

- [Line 14](../src/l6_2_interrupt_patterns/refunds.py#L14) now imports `Command` next to `interrupt`. In 6.1 only the caller used `Command` (to resume). Here a node returns one too.
- [`RefundState`](../src/l6_2_interrupt_patterns/refunds.py#L21-L39) still has no reducers, so every key a node returns replaces the old value. That is why the edited amount needs its own key: if `manager_review` wrote the edited amount into `amount`, the request would be lost. With two keys, `amount` stays what the customer asked for and `approved_amount` is what gets paid.
- `review_error` ([line 39](../src/l6_2_interrupt_patterns/refunds.py#L39)) carries a validation error from one run of `manager_review` to the next. A node keeps nothing between runs, so anything the next run must know has to be in the state. The type allows `None`, because an accepted answer writes `None` there to clear it.
- [`auto_approve`](../src/l6_2_interrupt_patterns/refunds.py#L59-L64) fills in `approved_amount` with the full amount. That way `pay_refund` can always read `approved_amount`, whoever approved the refund. Its return type became `dict[str, Any]` because the update now mixes a string and an int.

### [`check_answer`](../src/l6_2_interrupt_patterns/refunds.py#L71-L86)

A pure function, with no graph and no LangGraph import, so the first test can call it directly. It returns the message the manager will see, or `None`.

- [Line 81](../src/l6_2_interrupt_patterns/refunds.py#L81) checks the type first. `interrupt()` returns whatever the caller put in `Command(resume=...)`: a dict, a string, a number. A plain string like 6.1's `"approved"` fails here, before anything tries `answer["decision"]` on it.
- LangGraph hands a dict resume value to the node as it is. It would treat the dict as a map of interrupt ids only if every key were a 32-character hex id, so `{"decision": ...}` is safe. (Resuming by id is 6.3's topic.)
- [Line 83](../src/l6_2_interrupt_patterns/refunds.py#L83): a missing `amount` means "the full amount". So `{"decision": "approve"}` is valid, and so is a reject without an amount. A reject's amount is still checked here but never used after this.
- [Line 84](../src/l6_2_interrupt_patterns/refunds.py#L84) rejects a string such as `"120"` (the way an HTML form sends numbers), zero, and anything above the request. The `1 <= amount <= requested` range is the rule "a manager may lower a refund, never raise it". One gap to know about: in Python `True` is an `int` equal to 1, so `{"amount": True}` passes the check.

### [`manager_review`](../src/l6_2_interrupt_patterns/refunds.py#L97-L146)

The node where all three patterns meet. It calls `interrupt()` exactly once per run, and loops through the graph, not inside the node, when an answer is invalid.

- The return annotation on [line 99](../src/l6_2_interrupt_patterns/refunds.py#L99), `Command[Literal["pay_refund", "reject_refund", "manager_review"]]`, is read by `add_node`. It takes the names out of the `Literal` and stores them as the node's possible destinations: `builder.nodes["manager_review"].ends` becomes `("pay_refund", "reject_refund", "manager_review")` (the second test checks this). `compile()` uses that list to validate the targets, and `get_graph()` draws a dotted edge for each one, so the drawing shows a dotted self-loop on `manager_review`. Without the annotation the run still works, because `goto` is applied at run time. But `ends` is `()`, and the drawing shows a wrong edge to `__end__` instead. One of the experiments in the notes shows this.
- The print on [line 108](../src/l6_2_interrupt_patterns/refunds.py#L108) marks every start of the node, as in 6.1. In R-5 it now prints twice after each bad answer: once for the resumed run that checks the answer, and once for the new run that asks again.
- The `request` payload on [lines 109-113](../src/l6_2_interrupt_patterns/refunds.py#L109-L113) is the same data 6.1 passed to `interrupt()`. [Lines 116-117](../src/l6_2_interrupt_patterns/refunds.py#L116-L117) add the stored error to it, so the manager gets the same question plus the reason for asking again. On the first run `review_error` is not in the state, and `state.get` returns `None`.
- [Line 118](../src/l6_2_interrupt_patterns/refunds.py#L118) is the only `interrupt()` call. On the first run of the node it pauses the graph. When the run is a resume, it returns the answer.
- [Line 119](../src/l6_2_interrupt_patterns/refunds.py#L119) checks that answer. Each answer is checked exactly once: the run that received it either acts on it or rejects it, and nothing runs it again later (the fourth test counts the calls).
- [Line 128](../src/l6_2_interrupt_patterns/refunds.py#L128) is the validation pattern. The invalid answer is not acted on. `update` stores the error in `review_error`, and `goto="manager_review"` schedules the same node for the next step. That new run reads the error from the state, builds the payload with it, and reaches `interrupt()` with no resume value for it, so the graph pauses again, just like the first time: the checkpoint keeps `manager_review` pending, `invoke` returns, and `out.interrupts` holds the new payload. All of this happens inside one `invoke` call.
- The re-ask is a new pause from a new run of the node, so it has a new `Interrupt.id`. To tell a re-ask from the first question, read the `"error"` key in the payload.
- The Interrupts guide loops back with a conditional edge and a route function. The comment on [lines 121-127](../src/l6_2_interrupt_patterns/refunds.py#L121-L127) says why this node uses `Command(goto=...)` instead: it already routes with `Command`, so the self-loop uses the same mechanism as the other two exits.
- [Line 129](../src/l6_2_interrupt_patterns/refunds.py#L129) runs only once the answer passed `check_answer`. It replaces 6.1's "resumed with" print, so the output shows only the accepted answer.
- [Line 132](../src/l6_2_interrupt_patterns/refunds.py#L132) can safely use `answer["decision"]`: `check_answer` has already made sure `answer` is a dict with a valid decision.
- [Lines 133-136](../src/l6_2_interrupt_patterns/refunds.py#L133-L136) and [lines 139-145](../src/l6_2_interrupt_patterns/refunds.py#L139-L145) are the approve/reject pattern. A `Command` returned from a node does two things: LangGraph merges `update` into the state, as it does with a returned dict, and schedules the node named in `goto` for the next step. The human's answer, not an edge, picks the next node. The reject branch does not write `approved_amount`, so a rejected request never has that key. Both branches set `review_error` to `None`, so a decided request does not carry an old error.
- [Line 142](../src/l6_2_interrupt_patterns/refunds.py#L142) is the edit pattern. The manager's amount goes into `approved_amount`, or the requested amount if the manager sent none.

### [`pay_refund` and `reject_refund`](../src/l6_2_interrupt_patterns/refunds.py#L153-L162)

The two outcomes. Each one writes only `status`.

- [Line 155](../src/l6_2_interrupt_patterns/refunds.py#L155) reads `approved_amount`, never `amount`. This is where an edit takes effect: R-4 asked for \$300 and is paid \$120.
- `pay_refund` is reached from two places: from `auto_approve` through a normal edge, and from `manager_review` through `goto`. The node does not need to know which one it came from, because both put `approved_amount` in the state.

### [`build_graph`](../src/l6_2_interrupt_patterns/refunds.py#L169-L187)

- [Lines 181-182](../src/l6_2_interrupt_patterns/refunds.py#L181-L182) register the two new nodes. They must be registered under exactly the names used in the `Literal` and in `goto`. `compile()` checks the names in the annotation against the registered nodes.
- [Line 183](../src/l6_2_interrupt_patterns/refunds.py#L183) is the conditional edge from 6.1, unchanged.
- [Line 184](../src/l6_2_interrupt_patterns/refunds.py#L184): `auto_approve` no longer ends the run. It goes to `pay_refund`.
- There is no `add_edge` from `manager_review`, not even for the self-loop. Its `Command` chooses the next node. If you kept 6.1's `add_edge("manager_review", END)` as well, the run would still finish correctly, because `goto` still runs `pay_refund` or `reject_refund`. On 1.2.16 the output and even the drawing stay identical (as in lesson 3.3), so a leftover edge like that is easy to miss.
- [Lines 185-186](../src/l6_2_interrupt_patterns/refunds.py#L185-L186): both outcomes end the run.

## [\_\_main\_\_.py](../src/l6_2_interrupt_patterns/__main__.py)

The live run. Each region prints one section of the output.

- [`outcome`](../src/l6_2_interrupt_patterns/__main__.py#L21-L26) uses `values.get('approved_amount')` on [line 25](../src/l6_2_interrupt_patterns/__main__.py#L25) because a rejected request has no such key. That is the `approved_amount=None` in the R-3 output.
- Every invoke passes `version="v2"` (from 6.1). The result keeps the state in `out.value` and the pending interrupts in `out.interrupts`, so checking `out.interrupts` tells you whether the run paused.

### R-1: small refund ([lines 37-42](../src/l6_2_interrupt_patterns/__main__.py#L37-L42))

No pause. The path is `route_by_amount` → `auto_approve` → `pay_refund`, so the \$40 refund also prints a `[pay_refund]` line.

### R-2: approve ([lines 44-53](../src/l6_2_interrupt_patterns/__main__.py#L44-L53))

- [Line 47](../src/l6_2_interrupt_patterns/__main__.py#L47) reads the question from the first pending interrupt. `.value` is the `request` dict from `manager_review`.
- [Line 50](../src/l6_2_interrupt_patterns/__main__.py#L50) resumes with a dict, the kind of data a review form would post. On the restart `interrupt()` returns the dict, `check_answer` accepts it, and `manager_review` returns `Command(goto="pay_refund")`.

### R-3: reject ([lines 55-63](../src/l6_2_interrupt_patterns/__main__.py#L55-L63))

The first invoke's result is not stored on [line 57](../src/l6_2_interrupt_patterns/__main__.py#L57): the program already knows the request will pause. The only difference from R-2 is the resume value on [line 60](../src/l6_2_interrupt_patterns/__main__.py#L60). It sends the run to `reject_refund`, and no `[pay_refund]` line appears.

### R-4: edit ([lines 65-76](../src/l6_2_interrupt_patterns/__main__.py#L65-L76))

The resume on [lines 70-72](../src/l6_2_interrupt_patterns/__main__.py#L70-L72) carries `"amount": 120`. [Line 74](../src/l6_2_interrupt_patterns/__main__.py#L74) prints `amount` from the final state to show that the request (\$300) was kept next to the paid amount.

### R-5: validate ([lines 78-94](../src/l6_2_interrupt_patterns/__main__.py#L78-L94))

- The loop on [lines 84-92](../src/l6_2_interrupt_patterns/__main__.py#L84-L92) acts like a manager who tries three times. Each answer is a normal resume of the same thread (`config("R-5")`). The caller does nothing special after a bad answer: it just reads the new payload.
- [Line 91](../src/l6_2_interrupt_patterns/__main__.py#L91): a non-empty `out.interrupts` means the node asked again. [Line 92](../src/l6_2_interrupt_patterns/__main__.py#L92) prints the `"error"` from the new payload, which the new run of `manager_review` read from `review_error`. After `"yes"` the decision check fails. After `900` the amount check fails, because the limit is the request, \$180.
- After the third answer `out.interrupts` is empty, and [line 93](../src/l6_2_interrupt_patterns/__main__.py#L93) prints the final state with `approved_amount=150`.

## [test_patterns.py](../tests/test_patterns.py)

The tests check the same behaviour without relying on the printed text, except where a print is the evidence. Each graph test builds its own graph and saver.

- [`test_check_answer`](../tests/test_patterns.py#L19-L31) tests the validation rules without a graph. The `"120"` on [line 29](../tests/test_patterns.py#L29) is the form-string case.
- [`test_approve_and_reject_route_differently`](../tests/test_patterns.py#L34-L59) checks the destinations read from the annotation on [lines 37-41](../tests/test_patterns.py#L37-L41), including the self-loop. It then checks with `capsys` that R-3 never reaches `pay_refund` ([lines 58-59](../tests/test_patterns.py#L58-L59)).
- [`test_edited_amount_is_applied`](../tests/test_patterns.py#L62-L72) checks both amounts, the paid one and the kept one ([lines 70-71](../tests/test_patterns.py#L70-L71)).
- [`test_invalid_answers_are_asked_again`](../tests/test_patterns.py#L75-L120) checks the state of the thread after each answer. [Lines 79-86](../tests/test_patterns.py#L79-L86) wrap `check_answer` in a counter. This works because `manager_review` looks the name up in the module each time it runs. After each resume the counter is 1 (for example [line 94](../tests/test_patterns.py#L94)), which proves every answer is checked exactly once. After a bad answer `get_state().next` is still `("manager_review",)` ([line 99](../tests/test_patterns.py#L99)). After the good one `review_error` is cleared ([line 119](../tests/test_patterns.py#L119)) and `next` is `()` ([line 120](../tests/test_patterns.py#L120)). The test does not compare interrupt ids: it tells a re-ask apart by its `"error"` key.
- [`test_small_refund_goes_through_pay_refund`](../tests/test_patterns.py#L123-L134) compares the whole final state. This shows that `auto_approve` and `pay_refund` together write exactly the keys 6.1's `auto_approve` wrote, plus `approved_amount`. `review_error` is missing too, because only `manager_review` writes it.

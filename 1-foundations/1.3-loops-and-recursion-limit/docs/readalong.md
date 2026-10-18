# 1.3 Loops, Super-steps and the Recursion Limit — code walkthrough

The program takes the ticket router from lesson 1.2 and treats each queue node's reply as a first draft. A `check_reply` node lists the rules the draft still breaks. A `revise` node fixes one of them and goes back to `check_reply`, and the loop repeats until the reply is clean or the run is about to run out of super-steps. The program prints the graph, runs the three sample tickets, streams one run step by step, and then runs the first ticket with two small `recursion_limit` values. Run it with `./run.sh 1.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since 1.2

- [graph.py](../src/l1_3_loops_and_recursion_limit/graph.py#L22) imports `RemainingSteps` from `langgraph.managed`.
- New constants [`GREETING`, `URGENT_NOTE`, `SIGN_OFF`](../src/l1_3_loops_and_recursion_limit/graph.py#L33-L35) and [`STEPS_PER_REVISION`](../src/l1_3_loops_and_recursion_limit/graph.py#L39).
- [`TicketState`](../src/l1_3_loops_and_recursion_limit/graph.py#L59-L63) has two new keys, `problems` and the managed value `remaining_steps`.
- New nodes [`check_reply`](../src/l1_3_loops_and_recursion_limit/graph.py#L148-L160) and [`revise`](../src/l1_3_loops_and_recursion_limit/graph.py#L167-L182), and a new routing function [`route_after_check`](../src/l1_3_loops_and_recursion_limit/graph.py#L189-L200).
- In [`build_graph`](../src/l1_3_loops_and_recursion_limit/graph.py#L207-L257), the queue nodes lead to `check_reply` instead of `END` (lines 241–243). The new conditional edge is on lines 246–248, and the back edge `revise -> check_reply` that closes the loop is on line 253.
- In [`__main__.py`](../src/l1_3_loops_and_recursion_limit/__main__.py#L38-L41), the stream section numbers each update. The new section [`recursion_limit`](../src/l1_3_loops_and_recursion_limit/__main__.py#L44-L60) runs the first ticket with limits 9 and 5.
- [pyproject.toml](../pyproject.toml) now pins `langgraph==1.2.16`.
- [test_graph.py](../tests/test_graph.py) imports from the new package and expects the revised replies. It has new tests for `revise`, `route_after_check`, the loop in the stream and the recursion limit.

`clean`, `tag_priority`, `classify`, `route_ticket` and the three queue nodes are unchanged. They are explained in the [1.2 walkthrough](../../1.2-conditional-edges/docs/readalong.md).

## [graph.py](../src/l1_3_loops_and_recursion_limit/graph.py)

The state, the nodes, both routing functions and the wiring. Read it top to bottom.

- [`GREETING`, `URGENT_NOTE` and `SIGN_OFF`](../src/l1_3_loops_and_recursion_limit/graph.py#L33-L35) are the three rules. `check_reply` uses them to test the reply and `revise` uses them to fix it, so the two nodes always agree on what "fixed" means.
- [`STEPS_PER_REVISION`](../src/l1_3_loops_and_recursion_limit/graph.py#L39) is the cost of one round, counted in super-steps. A super-step is one tick of the graph: every node scheduled for that tick runs, and then the updates are merged. In this graph each tick runs exactly one node, so `revise` takes one super-step and the following `check_reply` takes another. The value 2 is not a tuning knob. If it is too small, the guard starts a round that cannot finish (see the experiments in the [notes](notes.md)).
- [`TicketState`](../src/l1_3_loops_and_recursion_limit/graph.py#L47-L63):
  - `problems` (line 59) is a plain channel with no reducer. Each `check_reply` replaces the whole list. It never appends to the old one.
  - `remaining_steps` (line 63) is different from every other key. Because its type is `RemainingSteps`, `StateGraph` does not create a channel for it. It registers a managed value instead. LangGraph computes it before each node and routing function call from the run's `recursion_limit` and the current step. It is never written by a node, never passed in by the caller, and it is left out of the `invoke()` result. That is why the printed results in `__main__.py` have no `remaining_steps` key.
- [`check_reply`](../src/l1_3_loops_and_recursion_limit/graph.py#L148-L160) only reads the state and returns `{"problems": [...]}`. The order of the three `if`s on lines 152–157 is the order `revise` fixes things in, because `revise` always takes the first entry. The urgent rule on line 154 depends on `priority`, which `tag_priority` wrote three super-steps earlier: the state keeps every key across the whole run, loop included.
- [`revise`](../src/l1_3_loops_and_recursion_limit/graph.py#L167-L182) reads `state["problems"][0]` on line 173. That works only because `revise` is reached only through `route_after_check`, which sends here only when the list is not empty. Called with an empty list, line 173 would raise `IndexError`. It returns only `{"reply": ...}`, so after it runs `problems` still describes the old reply. The back edge sends the new reply to `check_reply` again, and that is what makes `problems` correct again.
- [`route_after_check`](../src/l1_3_loops_and_recursion_limit/graph.py#L189-L200) is a routing function like `route_ticket`. It is not a node, it does not appear in the stream, and LangGraph calls it as part of `check_reply`'s super-step, after `check_reply`'s update has been merged. So on line 192, `state["problems"]` is the list `check_reply` has just written.
  - Line 198 is the guard. The router sees the same `remaining_steps` as the `check_reply` call that ran in the same super-step. A new round needs two more super-steps, and a node that runs with `remaining_steps == 0` is the last thing LangGraph allows before it raises `GraphRecursionError`. So a round may start only when at least 3 steps remain, which is why the guard sends when the value is `<= 2`. The tests on lines 79–80 of `test_graph.py` pin exactly this boundary.
  - Choosing `"send"` here does not fix anything. The reply goes out with the problems still listed in the state, so the caller can see the reply is not finished.
- [`build_graph`](../src/l1_3_loops_and_recursion_limit/graph.py#L207-L257) does the wiring.
  - Lines 220–221 register the two new nodes.
  - Lines 241–243: three plain edges into `check_reply`. Only one queue node runs per ticket, so `check_reply` is scheduled once, from whichever queue node ran.
  - Lines 246–248: the second conditional edge. The path map maps `"send"` to `END`, so the label in the routing function says what happens ("send"), and the map says where that leads. `END` is a valid path-map value like any node name.
  - Line 253: the back edge. Together with line 246 it forms the cycle `check_reply -> revise -> check_reply`. `compile()` on line 257 accepts the cycle without any warning. LangGraph does not check whether a loop can end. Only the routing function or the recursion limit stops it. If you delete line 253, nothing fails either: `revise` would have no outgoing edge, and the run would quietly end after one revision.

## [\_\_main\_\_.py](../src/l1_3_loops_and_recursion_limit/__main__.py)

The three sections from 1.2 and a new fourth one.

- Line 3: `GraphRecursionError` comes from `langgraph.errors`. It is a subclass of Python's built-in `RecursionError`, so `except RecursionError` would also catch it.
- Line 21: in the Mermaid output the loop shows up as `check_reply -.-> revise;` with no label, because the label `revise` equals the node name. `check_reply -. &nbsp;send&nbsp; .-> __end__;` keeps its label, and `revise --> check_reply;` is the solid back edge.
- Line 30: every result now ends with `'problems': []`, and the reply has the greeting and sign-off. Only the urgent billing ticket gets the urgent note. You cannot see from the result how many rounds a ticket took. The stream section shows that.
- Lines 38–41: `enumerate(..., start=1)` numbers the updates. The comment's claim holds because no super-step here runs two nodes in parallel. The refund ticket prints 11 lines: four steps to reach `billing_queue`, the first `check_reply`, then three `revise` and `check_reply` rounds, one per problem.
- [Lines 44–60](../src/l1_3_loops_and_recursion_limit/__main__.py#L44-L60): the second argument to `invoke()` on line 52 is the run config. `recursion_limit` applies to this one call only. The compiled graph is not changed, so the same `graph` object is reused for both limits. Without the key, LangGraph 1.2.16 uses its default of 10007.
  - With limit 9: `remaining_steps` is 8 in step 1 and drops by one each step. The first `check_reply` runs in step 5 with 4 left, so the router starts a round. The second `check_reply` runs in step 7 with 2 left, so the guard sends. The result has the greeting only, and the problems `['urgent_note', 'sign_off']`.
  - With limit 5: the first `check_reply` already runs in step 5 with 0 left. The router does choose `"send"`, but a node that ran with 0 remaining is the last step LangGraph allows, so it raises anyway. The guard can only shorten the loop. It cannot make room for the four steps before the loop.
  - Line 54 keeps only the first line of the message. The full message has a second line with a troubleshooting URL.
  - The `else:` branch on line 56 runs only when `invoke()` did not raise, so `result` is always set there.

## [test_graph.py](../tests/test_graph.py)

Offline tests for the loop and the limit.

- [`test_clean_returns_partial_update`](../tests/test_graph.py#L23-L26) and [`test_route_ticket_returns_label`](../tests/test_graph.py#L54-L63) are the 1.2 tests with the new import.
- [`test_ticket_routed_and_reply_revised`](../tests/test_graph.py#L29-L44) runs each branch to the end. The exact replies check both the rules and their order: the urgent note sits between the queue text and the sign-off because `check_reply` lists it before `sign_off`.
- [`test_billing_checked_before_tech`](../tests/test_graph.py#L47-L51) now also checks that a billing ticket with normal priority gets no urgent note.
- [`test_revise_fixes_only_first_problem`](../tests/test_graph.py#L66-L72) and [`test_route_after_check`](../tests/test_graph.py#L75-L86) call the functions directly with a partial dict. In a direct call nothing fills in `remaining_steps`, so the test passes it by hand. Only a running graph computes it.
- [`test_stream_shows_the_loop`](../tests/test_graph.py#L89-L105) checks the order of the 11 nodes and that the last update is an empty problem list.
- [`test_recursion_limit_graceful_stop_and_error`](../tests/test_graph.py#L108-L115) checks the two outcomes of section 4: a partly revised reply with limit 9, and `pytest.raises(GraphRecursionError)` with limit 5.
- [`test_mermaid_draws_loop`](../tests/test_graph.py#L118-L131) checks the loop's arrows, and checks on line 131 that the old `billing_queue --> __end__` edge is gone.

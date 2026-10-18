# 1.2 Conditional Edges and Routing — code walkthrough

The program takes the ticket pipeline from lesson 1.1, adds a `classify` step, and then uses a conditional edge to send each ticket to exactly one of three queue nodes: billing, tech or general. It prints the graph as Mermaid, runs it on one ticket for each queue, and streams the updates for a fourth ticket so you can see that only one queue node ran. Run it with `./run.sh 1.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since 1.1

- [graph.py](../src/l1_2_conditional_edges/graph.py#L12): `Literal` is imported next to `TypedDict`.
- New keyword tuples [`BILLING_KEYWORDS`](../src/l1_2_conditional_edges/graph.py#L20) and [`TECH_KEYWORDS`](../src/l1_2_conditional_edges/graph.py#L22), and the type alias [`Category`](../src/l1_2_conditional_edges/graph.py#L26).
- [`TicketState`](../src/l1_2_conditional_edges/graph.py#L40-L41) has two new keys, `category` and `reply`.
- New node [`classify`](../src/l1_2_conditional_edges/graph.py#L74-L87), new routing function [`route_ticket`](../src/l1_2_conditional_edges/graph.py#L94-L100), and three new queue nodes [`billing_queue`, `tech_queue`, `general_queue`](../src/l1_2_conditional_edges/graph.py#L107-L119).
- In [`build_graph`](../src/l1_2_conditional_edges/graph.py#L126-L164), `tag_priority` now leads to `classify` instead of `END` (line 143). The conditional edge is added on lines 151–155, and each queue node gets its own edge to `END` on lines 158–160.
- [`SAMPLE_TICKETS`](../src/l1_2_conditional_edges/__main__.py#L5-L9) in `__main__.py` now holds three tickets, one for each queue. Everything else in `main` stays the same.
- [test_graph.py](../tests/test_graph.py) imports from the new package. It has new routing tests, and the stream and Mermaid tests now check the new nodes.

`clean` and `tag_priority` are unchanged. Their explanation is in the [1.1 walkthrough](../../1.1-hello-graph/docs/readalong.md).

## [graph.py](../src/l1_2_conditional_edges/graph.py)

The state, all six nodes, the routing function and the wiring. Read it top to bottom.

- [`BILLING_KEYWORDS`](../src/l1_2_conditional_edges/graph.py#L20) and [`TECH_KEYWORDS`](../src/l1_2_conditional_edges/graph.py#L22) are substring lists like `URGENT_KEYWORDS`. The tuples overlap: "refund" is both urgent and billing, and "down" is both urgent and tech. That is why the first sample ticket comes out as `billing` with priority `high`. Priority and category are decided separately.
- [`Category`](../src/l1_2_conditional_edges/graph.py#L26) is an ordinary `typing.Literal` alias. It is used twice: as the type of the `category` state key (line 40) and as `route_ticket`'s return annotation (line 94). Because this graph passes a dict path map, LangGraph never reads the annotation. It documents the labels and lets a type checker check them. Without a path map, LangGraph would treat these labels as node names (see `build_graph` below).
- [`TicketState`](../src/l1_2_conditional_edges/graph.py#L30-L41) gets `category` and `reply` on lines 40–41. Each new key is one more channel. `reply` has no reducer, and that works only because exactly one queue node writes it per run. If two nodes wrote `reply` in the same step, LangGraph would raise `InvalidUpdateError`.
- [`classify`](../src/l1_2_conditional_edges/graph.py#L74-L87) is a normal node: it reads `clean_text` and returns only `{"category": ...}`. The `if`/`elif` order on lines 79–84 is the tie-break, so "Payment page shows an error" becomes `billing`. Making the decision in a node rather than in the edge means the category goes into the state. It shows up in the `invoke()` result and in the stream, and the next lessons can read it.
- [`route_ticket`](../src/l1_2_conditional_edges/graph.py#L94-L100) is not a node. It is not registered with `add_node` and never appears in the stream. LangGraph calls it right after `classify`, as part of the same step, with the state that already contains `classify`'s update. That is why `state["category"]` on line 100 is already set. Its return value is a label for the edge, not a state update. A dict returned here would not be merged into the state.
  - Because `TicketState.category` is typed as `Category`, line 100 type-checks without any suppression comment: the value read from the state already has the type the function promises.
- [`billing_queue`, `tech_queue` and `general_queue`](../src/l1_2_conditional_edges/graph.py#L107-L119) each return a fixed `reply`. They do not use `state`. They take it anyway because LangGraph always calls a node with the state. They are kept as separate flat functions so that lesson 1.3 can extend them.
- [`build_graph`](../src/l1_2_conditional_edges/graph.py#L126-L164) does the wiring.
  - Lines 135–138 register the four new nodes. Nothing connects to the queue nodes with `add_edge`. The conditional edge is their only way in.
  - Line 143 replaces 1.1's `tag_priority -> END`, so the pipeline now continues to `classify`.
  - Lines 151–155: `add_conditional_edges("classify", route_ticket, {...})`. LangGraph stores this as a branch on `classify`. After `classify` finishes, it calls `route_ticket`, looks the returned label up in the path map on line 154, and schedules only that one node for the next step. The path map has two jobs:
    - It translates labels into node names. A label that is not in the map raises `KeyError` at run time, but only when a ticket actually takes that route.
    - It lists every possible destination. `compile()` checks that each one is a real node, and `get_graph()` draws one dotted arrow per entry. With no path map, LangGraph falls back to the `Literal` labels as node names, and `compile()` fails here because there is no node called `billing`.
  - Lines 158–160: each queue node needs its own edge to `END`. Without one, that node would have no outgoing edge, and the run would simply stop after it.
  - Line 164: `compile()` now also checks the branch's destinations against the registered nodes.

## [\_\_main\_\_.py](../src/l1_2_conditional_edges/__main__.py)

The same three sections as in 1.1. Only the data changed.

- [`SAMPLE_TICKETS`](../src/l1_2_conditional_edges/__main__.py#L5-L9) has one ticket for each branch, so a single run exercises all three paths.
- Line 19: in the Mermaid output, the conditional edges appear as dotted arrows labelled with the path-map keys, for example `classify -. &nbsp;billing&nbsp; .-> billing_queue;`. Plain edges stay solid `-->`. The edges are not printed in the order `build_graph` added them: the edges into `__end__` come last.
- Line 28: each `invoke()` result has all five keys. `reply` comes from whichever queue node ran, and `category` shows why that node was chosen.
- Line 36: the stream prints four updates: `clean`, `tag_priority`, `classify`, `billing_queue`. Nothing comes from `route_ticket`, because it is part of the edge, not a node. The other two queue nodes never appear, because they never ran.

## [test_graph.py](../tests/test_graph.py)

Offline tests for the routing.

- [`test_clean_returns_partial_update`](../tests/test_graph.py#L11-L14) is the 1.1 test, unchanged. The input dict on line 13 has no `category` or `reply`. That is fine, because `clean` only reads `text`.
- [`test_ticket_routed_to_matching_queue`](../tests/test_graph.py#L17-L31) runs every branch through the real graph and also checks each ticket's priority (the refund ticket is both urgent and billing). This matters because a broken path-map entry only fails when a ticket takes that route.
- [`test_billing_checked_before_tech`](../tests/test_graph.py#L34-L38) pins down the tie-break order in `classify`.
- [`test_route_ticket_returns_label`](../tests/test_graph.py#L41-L50) calls the routing function directly, like any plain function, and checks that it returns the string `"tech"`, not a dict.
- [`test_stream_runs_only_one_queue`](../tests/test_graph.py#L53-L63) checks on lines 56–61 that exactly one queue node ran.
- [`test_mermaid_draws_conditional_edges`](../tests/test_graph.py#L66-L77) checks the dotted labelled arrows, and checks on line 77 that the old `tag_priority --> __end__` edge is gone.

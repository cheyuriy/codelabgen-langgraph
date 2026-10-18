# 1.1 Your First Graph: State, Nodes and Edges — code walkthrough

The program builds a two-step LangGraph pipeline that tidies a raw support ticket and tags its priority. It then prints the graph as Mermaid, runs it on two tickets, and streams the per-node updates for a third. Run it with `./run.sh 1.1` from the course root.
The concept itself is explained in the [notes](notes.md).

## [graph.py](../src/l1_1_hello_graph/graph.py)

The whole graph lives here: the state, the two nodes, and the function that wires them together. Read it top to bottom.

- [`URGENT_KEYWORDS`](../src/l1_1_hello_graph/graph.py#L16) is a plain tuple. The node treats it as substrings, not whole words, so "download" also counts as urgent because it contains "down". That is good enough for a first step. Later lessons build on this file, so it is kept simple on purpose.
- [`TicketState`](../src/l1_1_hello_graph/graph.py#L20-L29) is the graph's schema. `StateGraph` reads its keys and creates one channel for each, so `text`, `clean_text` and `priority` are the only keys the graph knows about. If a node returns a key that is not listed here, LangGraph quietly drops it. A typo in a returned key therefore produces no error, just a missing value in the result.
  - It is a plain `TypedDict` (not `total=False`), but the graph is still invoked with only `text`. LangGraph does not check the `TypedDict` at run time. A key no node has written yet is just absent from the state.
  - None of the keys has a reducer, so a returned value replaces the old one (lines 23–24 say this). Reducers come in later lessons.
- [`clean`](../src/l1_1_hello_graph/graph.py#L36-L43) is an ordinary function. LangGraph calls it with the current state as a dict and treats the returned dict as an update.
  - Line 40: `split()` with no arguments splits on any run of whitespace, newlines included, and drops the ends. `" ".join(...)` puts the words back together with single spaces.
  - Line 43 returns only `clean_text`. LangGraph merges this into the state, so `text` stays exactly as the customer typed it. That is why the `invoke()` output still shows the original `text` with its newline and extra spaces. If `clean` returned `{**state, ...}` with a changed `text`, the original would be overwritten.
- [`tag_priority`](../src/l1_1_hello_graph/graph.py#L50-L55) reads `state["clean_text"]` on line 54. That key exists only because the edge from `clean` makes this node run after `clean`, and by then `clean`'s update has been merged. The node checks the cleaned text, so "DOWN" and "ASAP" match even though the raw text is in upper case.
- [`build_graph`](../src/l1_1_hello_graph/graph.py#L62-L79) does the wiring. It is kept flat so that lesson 1.2 can add nodes and a conditional edge here.
  - Line 65: `StateGraph(TicketState)` makes a builder. It cannot run anything yet. It only collects nodes and edges.
  - Lines 69–70: `add_node` registers each function under a string name. From now on edges refer to the node by that name, not by the function.
  - Lines 73–75: `START` and `END` are constants for the virtual entry and exit points. Their string values are `"__start__"` and `"__end__"`, which is what you see in the Mermaid output. The edge from `START` in line 73 decides which node receives the input first. The edges alone decide the order, not the order of the `add_node` calls.
  - Line 79: `compile()` checks the wiring and returns a `CompiledStateGraph`, which has `invoke`, `stream` and `get_graph`. Wiring mistakes show up here, before any ticket is processed: a missing edge from `START` and an edge to an unknown node name both raise `ValueError`. A node that no edge reaches is not an error. It simply never runs.

## [\_\_main\_\_.py](../src/l1_1_hello_graph/__main__.py)

The entry point that `python -m l1_1_hello_graph` runs. [`main`](../src/l1_1_hello_graph/__main__.py#L11-L35) builds the graph once on line 13 and reuses it for every call, because a compiled graph has no per-run state of its own.

- [`SAMPLE_TICKETS`](../src/l1_1_hello_graph/__main__.py#L5-L8): the first ticket has messy whitespace and urgent words, so it comes out `high`. The second has neither, so it comes out `normal`.
- Line 18: `get_graph()` turns the compiled graph into a drawable description of its nodes and edges. `draw_mermaid()` renders that description as Mermaid text locally. It does not run the graph or touch the network. You can paste the output into any Mermaid viewer.
- Line 26: `invoke()` runs the graph from `START` to `END` and returns the final state as a plain dict. The input dict only fills `text`. The result holds all three keys because the two node updates were merged in along the way.
- Line 33: `stream(..., stream_mode="updates")` runs the same graph but yields one item per node, shaped `{node_name: what_the_node_returned}`. In the output you get `{'clean': {'clean_text': 'refund please'}}` and then `{'tag_priority': {'priority': 'high'}}`, which shows that each node returned only its own key. Streaming itself is covered in a later lesson; here it only makes the partial updates visible.

## [test_graph.py](../tests/test_graph.py)

Offline tests for the same behaviour. They need no network and no LLM.

- [`test_clean_returns_partial_update`](../tests/test_graph.py#L8-L11) calls `clean` directly, without a graph. A node is just a function, so you can test it by passing in a dict. The `==` on line 11 also confirms that it returns exactly one key.
- [`test_urgent_ticket_is_high_and_text_kept`](../tests/test_graph.py#L14-L18) checks on line 18 that the merge left `text` alone.
- [`test_stream_updates_per_node`](../tests/test_graph.py#L28-L33) checks the node order and that each update holds only that node's key.
- [`test_mermaid_has_edges`](../tests/test_graph.py#L36-L40) checks the drawn edges, using the `__start__`/`__end__` names that `START` and `END` stand for.

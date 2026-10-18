# 8.1 Subgraphs with Shared State — code walkthrough

The program is a small support desk. It classifies a ticket and sends it either to a plain `general` node or to `billing`, a whole compiled graph used as one node. The run shows four things: what comes back from the subgraph, the nested drawing with `get_graph(xray=True)`, namespaced updates with `stream(subgraphs=True, version="v2")`, and the subgraph's checkpoints in the parent's saver. Run it with `./run.sh 8.1` from the course root.
The concept itself is explained in the [notes](notes.md).

## Where the code comes from

This is the first lesson of module 8, and its example ("support-desk") is new. Lessons 8.2 and 8.3 extend it. That is why the billing team lives in its own file with a `build_billing()` that takes no parameters, why `build_desk` takes the saver as a parameter (as in [lesson 5.1](../../../5-persistence/5.1-checkpointers-and-threads/docs/readalong.md)), and why the teams are a `Category` literal plus a path map: 8.2 adds one more team in each place.

[pyproject.toml](../pyproject.toml#L6-L10) pins `langgraph`, `langgraph-checkpoint` and `langchain-core`, the same pins as 5.1. The code imports `langchain_core.messages` and `langgraph.checkpoint.memory` directly, so both packages are listed even though `langgraph` installs them anyway. There is no model and no service: every node writes a fixed message, so the run is offline and prints the same lines every time.

## [billing.py](../src/l8_1_subgraphs_shared_state/billing.py)

The billing team as a graph of its own: two nodes in a line. It knows nothing about the desk.

- [`BillingState`](../src/l8_1_subgraphs_shared_state/billing.py#L13-L22) has two keys. `messages` on [line 19](../src/l8_1_subgraphs_shared_state/billing.py#L19) is declared exactly like the desk's `messages`: same name, same type, same `add_messages` reducer. The name is what connects the two graphs. When the desk runs the subgraph, the subgraph reads the desk's value of every key it also has, and when it finishes, its final value of those keys goes back. Nothing else is configured anywhere.
- `invoice_id` on [line 22](../src/l8_1_subgraphs_shared_state/billing.py#L22) is a key only the subgraph has. It is a normal channel while the subgraph runs, so `draft_reply` can read what `find_invoice` wrote. The desk has no channel with that name, so the value has nowhere to go when the subgraph ends. `NotRequired` is there because the input from the desk does not contain it.
- [`find_invoice`](../src/l8_1_subgraphs_shared_state/billing.py#L29-L34) reads the last message on [line 33](../src/l8_1_subgraphs_shared_state/billing.py#L33). The subgraph never wrote a message at that point: the customer's ticket is there only because the desk passed its `messages` in. The regex looks for `INV-` followed by digits; a ticket without one, like the test's "I want a refund", gets `"unknown"` on [line 34](../src/l8_1_subgraphs_shared_state/billing.py#L34) instead of an error.
- [`draft_reply`](../src/l8_1_subgraphs_shared_state/billing.py#L37-L41) returns a list with one new `AIMessage`. Inside the subgraph, the `add_messages` reducer appends it to the ticket, so the subgraph's `messages` ends with two messages. `name="billing"` on [line 41](../src/l8_1_subgraphs_shared_state/billing.py#L41) is an ordinary message field; `label` in `show.py` prints it, so the output says which team answered.
- [`build_billing`](../src/l8_1_subgraphs_shared_state/billing.py#L48-L61) wires `START -> find_invoice -> draft_reply -> END` and calls `compile()` on [line 61](../src/l8_1_subgraphs_shared_state/billing.py#L61) without a `checkpointer`. The default is `None`, which does not mean "never save": it means "use whatever saver the parent lends me". Section 4 of the run shows the result. `checkpointer=False` would turn that off (experiment 2).

## [desk.py](../src/l8_1_subgraphs_shared_state/desk.py)

The parent graph: classify the ticket, then route it to one of two nodes. One of them is the billing subgraph.

- [`BILLING_KEYWORDS`](../src/l8_1_subgraphs_shared_state/desk.py#L14) is the word list from lesson 1.2. [`Category`](../src/l8_1_subgraphs_shared_state/desk.py#L17) lists the teams; it is the type of the `category` key and the return type of the router, and its values are the keys of the path map further down.
- [`DeskState`](../src/l8_1_subgraphs_shared_state/desk.py#L21-L28) repeats the `messages` declaration from `BillingState` on [line 25](../src/l8_1_subgraphs_shared_state/desk.py#L25). The reducer matters here more than inside the subgraph, as the `build_desk` comment explains. `category` on [line 28](../src/l8_1_subgraphs_shared_state/desk.py#L28) is the parent's own key; `BillingState` has no such key, so the subgraph never receives it and cannot write it.
- [`classify`](../src/l8_1_subgraphs_shared_state/desk.py#L35-L39) lowercases the last message and stores a decision. [`route_ticket`](../src/l8_1_subgraphs_shared_state/desk.py#L42-L44) only reads that decision back, the same split between a node that decides and a router that reads as in lesson 1.2. Storing the decision in state is also why `category` is still in the final result.
- [`general`](../src/l8_1_subgraphs_shared_state/desk.py#L47-L50) is a plain function node that answers everything else. It is there so the tests can show a run that never enters the subgraph.
- [`build_desk`](../src/l8_1_subgraphs_shared_state/desk.py#L57-L86) is the heart of the lesson. [Line 76](../src/l8_1_subgraphs_shared_state/desk.py#L76) passes the compiled graph from `build_billing()` to `add_node`, exactly where a function would go. `add_node` accepts any runnable, and a compiled graph is one: when the node runs, the desk invokes it with its current state and treats what it returns as the node's update. There is no wrapper function and no key mapping, which is only possible because the schemas share `messages`. With different schemas you call the subgraph inside a node and map the keys yourself (lesson 8.2).
- The long comment above line 76 describes the merge, and the run proves it in section 3. The update the `billing` node writes is the subgraph's final `messages`: the ticket **and** the reply, as one list. The parent applies it with its own reducer. `add_messages` merges by message id ([lesson 4.1](../../../4-agents/4.1-messages-state/docs/notes.md#messagesstate-and-add_messages); reducers in general are in [lesson 2.2](../../../2-state/2.2-reducers/docs/notes.md#the-concept)). The ticket in the update has the same id as the ticket already in the parent, so it replaces itself, and only the reply is added. A reducer that appends, such as `operator.add`, would store the ticket twice (experiment 1). This is the trap of shared list keys.
- The conditional edge on [lines 79-81](../src/l8_1_subgraphs_shared_state/desk.py#L79-L81) maps each `Category` value to a node name. The node is named `"billing"` like the category; that name is also what later shows up as the subgraph's namespace (`billing:<task_id>`) and as the `subgraph billing` block in the drawing.
- [Line 86](../src/l8_1_subgraphs_shared_state/desk.py#L86) gives the checkpointer to the parent only. `None` is allowed, which is how two tests build the desk without a saver and without a `thread_id`.

## [show.py](../src/l8_1_subgraphs_shared_state/show.py)

Three helpers that turn run data into short, stable text. They exist so the output never contains ids that change on every run.

- [`label`](../src/l8_1_subgraphs_shared_state/show.py#L9-L11) prints `message.name` when it is set (`"billing"`, `"general"`) and falls back to `message.type` otherwise. The ticket is a `HumanMessage` without a name, so it shows as `human`.
- [`node_path`](../src/l8_1_subgraphs_shared_state/show.py#L14-L21) turns a namespace into node names. A namespace is a tuple with one `"node_name:<task_id>"` string per level of nesting, for example `("billing:3f2a…",)`. The part after the colon is a fresh uuid every time, so line 21 keeps only what comes before it and joins the levels with `/` (a test checks that `("desk:1", "billing:2")` becomes `desk/billing`). The top-level graph has the empty namespace `()`; the join then gives `""`, which is falsy, so `or "(root)"` takes over.
- The same function reads checkpoint namespaces in section 4. There the namespace is one string with the levels joined by `|` (empty for the parent), so the caller splits it first. `"".split("|")` is `[""]`, not `[]`, but that still joins to `""` and prints `(root)`.
- [`brief`](../src/l8_1_subgraphs_shared_state/show.py#L24-L29) copies an update dict and replaces a `messages` list with the labels of its messages. Other keys, like `category` or `invoice_id`, are short already and stay as they are. That is how section 3 can show that the root `billing` update holds two messages, `['human', 'billing']`, without printing them in full.

## [\_\_main\_\_.py](../src/l8_1_subgraphs_shared_state/__main__.py)

The live run. [`BILLING_TICKET`](../src/l8_1_subgraphs_shared_state/__main__.py#L11) contains both a keyword ("refund") and an invoice number, so it goes to billing and `find_invoice` finds `INV-1042`. [`GENERAL_TICKET`](../src/l8_1_subgraphs_shared_state/__main__.py#L13) is not used by the run; it is defined here so the tests and the experiments can import it.

[`main`](../src/l8_1_subgraphs_shared_state/__main__.py#L16-L90) builds one `InMemorySaver` and one desk on [lines 18-19](../src/l8_1_subgraphs_shared_state/__main__.py#L18-L19) and prepares two thread configs. Sections 1 and 4 look at thread `ticket-1`; section 3 uses `ticket-2`, so its message count starts from an empty thread.

### Section 1: the result ([lines 23-32](../src/l8_1_subgraphs_shared_state/__main__.py#L23-L32))

`invoke` on [line 25](../src/l8_1_subgraphs_shared_state/__main__.py#L25) runs `classify`, then the whole subgraph as the `billing` node. The loop prints two messages: the ticket and the billing reply, with no duplicate. [Line 30](../src/l8_1_subgraphs_shared_state/__main__.py#L30) prints the keys of the final state: `category` and `messages`. `invoice_id` is missing, because the parent has no channel for it. `category` is present, because only the parent wrote it and the subgraph's update does not contain it.

### Section 2: the drawing ([lines 34-44](../src/l8_1_subgraphs_shared_state/__main__.py#L34-L44))

`get_graph()` on [line 40](../src/l8_1_subgraphs_shared_state/__main__.py#L40) draws the desk as the desk sees it: `billing` is one node. With `xray=True` on [line 41](../src/l8_1_subgraphs_shared_state/__main__.py#L41), LangGraph asks the graph for its subgraphs (`get_subgraphs()`, the same call section 4 uses), draws each one inside and drops the single `billing` box. The inner nodes get ids prefixed with the node name, `billing:find_invoice`, so they cannot clash with parent nodes of the same name. The edges from `classify` and to `__end__` are rewired to the subgraph's first and last nodes.

[Line 43](../src/l8_1_subgraphs_shared_state/__main__.py#L43) prints the Mermaid text. The `subgraph billing … end` block is Mermaid's own grouping syntax, and `\3a` in the ids is the escaped colon. The text ends with a newline, so `print` leaves the blank line after this section without an extra `print()`.

### Section 3: streaming from both levels ([lines 46-68](../src/l8_1_subgraphs_shared_state/__main__.py#L46-L68))

The `stream` call on [lines 53-59](../src/l8_1_subgraphs_shared_state/__main__.py#L53-L59) combines three arguments. `stream_mode="updates"` reports what each node returned. `subgraphs=True` makes the desk forward the subgraph's own parts too; without it the subgraph is streamed as one node and only two lines appear (experiment 3). `version="v2"` makes every part a dict with `type`, `ns` and `data` ([lesson 7.1](../../../7-streaming/7.1-stream-modes/docs/notes.md#the-v2-format-one-shape-for-every-chunk)). In 7.1 `ns` was always `()`; here it finally says where a part came from. In v1 the same call yields `(ns, chunk)` tuples, and `part["data"]` on line 60 would fail.

The loop on [lines 60-61](../src/l8_1_subgraphs_shared_state/__main__.py#L60-L61) prints one line per node update, `:<8` pads the path so the columns line up. Read the four lines from top to bottom: `classify` in the root, the two subgraph nodes under `billing`, then the root `billing` node with its merged update, which holds both messages. [Line 65](../src/l8_1_subgraphs_shared_state/__main__.py#L65) counts the messages in the saved thread: 2, not 3, because `add_messages` recognised the ticket by its id.

### Section 4: one saver, two namespaces ([lines 70-90](../src/l8_1_subgraphs_shared_state/__main__.py#L70-L90))

[Line 78](../src/l8_1_subgraphs_shared_state/__main__.py#L78) gets the compiled subgraph back from the desk: `get_subgraphs()` yields `(node_name, graph)` pairs, and `dict(...)` makes them searchable by name. [Line 79](../src/l8_1_subgraphs_shared_state/__main__.py#L79) prints its `checkpointer` attribute: `None`, as compiled in `build_billing`.

Still, the parent's saver holds the subgraph's checkpoints. When the desk runs a node, it puts its own checkpointer into that task's config; a subgraph compiled with `None` picks the lent saver up when it starts. The code comment names the two places in the 1.2.16 source. The subgraph saves under its own `checkpoint_ns`, `billing:<task_id>`, so its history does not mix with the parent's.

`checkpointer.list(ticket_1)` on [line 87](../src/l8_1_subgraphs_shared_state/__main__.py#L87) passes only a `thread_id`, so `InMemorySaver` returns the checkpoints of every namespace in that thread. The `Counter` on [lines 85-88](../src/l8_1_subgraphs_shared_state/__main__.py#L85-L88) groups them by `node_path`, and the loop prints 4 for each graph: the input checkpoint plus one per super-step ([lesson 5.1](../../../5-persistence/5.1-checkpointers-and-threads/docs/notes.md#when-checkpoints-are-written)). The parent has three steps (input, `classify`, `billing`); the subgraph has three as well (input, `find_invoice`, `draft_reply`). `sorted` puts `(root)` first because `(` sorts before letters.

Because the namespace contains the task id, the next run of the subgraph in the same thread gets a new namespace and starts a fresh history; the last test checks that. Reading the subgraph's saved state with `get_state(..., subgraphs=True)` is lesson 8.2's topic.

## [test_subgraphs.py](../tests/test_subgraphs.py)

The tests check the same facts as the run, plus the cases the run does not show. [`_config`](../tests/test_subgraphs.py#L14-L16) builds a thread config.

- [`test_billing_ticket_only_shared_keys_come_back`](../tests/test_subgraphs.py#L19-L31) checks the two messages, `category == "billing"` and the missing `invoice_id`, then sends a ticket without an invoice number on a second thread and expects `unknown` in the reply.
- [`test_general_ticket_never_enters_subgraph`](../tests/test_subgraphs.py#L34-L50) builds the desk with `None`, so `stream` needs no config. Even with `subgraphs=True` there are only two parts, both with `ns == ()`: the router never chose `billing`, so the subgraph never ran.
- [`test_stream_with_subgraphs_shows_both_levels`](../tests/test_subgraphs.py#L53-L90) checks the order of the four `(path, node)` pairs, that each billing part has a one-level namespace starting with `billing:` (without comparing the uuid), the `brief` of the merged update and the count of 2. The second stream, without `subgraphs=True`, leaves only the two root pairs.
- [`test_xray_draws_subgraph_nodes`](../tests/test_subgraphs.py#L93-L108) compares the node ids of both drawings and checks the `subgraph billing` block. It compares a `set` for the xray nodes, so it does not depend on the order in which the drawing lists them.
- [`test_parent_checkpointer_saves_subgraph_checkpoints`](../tests/test_subgraphs.py#L111-L135) is section 4 with a second run added: after it the counts double to 8 and 8, and there are two different non-empty namespaces, one per subgraph run. It counts them instead of comparing raw ids.
- [`test_show_helpers`](../tests/test_subgraphs.py#L138-L145) pins down `node_path` for the root, one level, two levels and an empty checkpoint namespace, and `label` with and without a name.

# 8.2 Subgraphs with Their Own State — code walkthrough

The support desk from 8.1 gets a third team, tech. The tech team is a graph with its own state, and none of its keys match the desk's keys. The desk therefore calls it from inside a plain node function that translates the state in both directions. The run shows a tech ticket, the two ways of attaching a subgraph side by side in the stream, a ticket that pauses inside the tech subgraph, how that paused state is read with `get_state(subgraphs=True)`, and the resume. Run it with `./run.sh 8.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 8.1

The billing team, the desk state and the print helpers are the same as in 8.1. For those parts, read the [8.1 walkthrough](../../8.1-subgraphs-shared-state/docs/readalong.md).

- New file [tech.py](../src/l8_2_subgraphs_own_state/tech.py): `TechState`, two nodes, and `build_tech()`.
- [desk.py](../src/l8_2_subgraphs_own_state/desk.py): [`TECH_KEYWORDS`](../src/l8_2_subgraphs_own_state/desk.py#L19), `"tech"` added to [`Category`](../src/l8_2_subgraphs_own_state/desk.py#L22), a tech branch in [`classify`](../src/l8_2_subgraphs_own_state/desk.py#L45-L46), the new region with [`TECH_TEAM`](../src/l8_2_subgraphs_own_state/desk.py#L72) and the wrapper node [`tech`](../src/l8_2_subgraphs_own_state/desk.py#L75-L99), and three new lines in [`build_desk`](../src/l8_2_subgraphs_own_state/desk.py#L130-L139).
- [billing.py](../src/l8_2_subgraphs_own_state/billing.py#L59-L60): only one sentence of a comment changed. [show.py](../src/l8_2_subgraphs_own_state/show.py) is unchanged.
- [\_\_main\_\_.py](../src/l8_2_subgraphs_own_state/__main__.py) is rewritten: two new tickets and four new sections. The 8.1 run is still in lesson 8.1.
- [test_own_state.py](../tests/test_own_state.py) replaces the 8.1 tests. The 8.1 assertion about the xray drawing no longer holds, because the desk now has a second subgraph.
- [pyproject.toml](../pyproject.toml) has the same three pins as 8.1.

## [tech.py](../src/l8_2_subgraphs_own_state/tech.py)

The tech team as a graph of its own. It imports nothing from the desk, and that is the point of the lesson.

- [`DEVICES`](../src/l8_2_subgraphs_own_state/tech.py#L10) and [`FIXES`](../src/l8_2_subgraphs_own_state/tech.py#L13-L17) are fixed data, so the run gives the same output every time and needs no model.
- [`TechState`](../src/l8_2_subgraphs_own_state/tech.py#L21-L34) has `problem`, `device` and `fix`. In 8.1, `messages` was the bridge between the graphs: a key with the same name in both schemas is a channel they share. Here there is no such key. If you added this graph to the desk with `add_node` directly, it would get an empty input (8.1 experiment 4), and `identify_device` would fail on `state["problem"]`. `device` and `fix` are `NotRequired` because the input contains only `problem`.
- [`identify_device`](../src/l8_2_subgraphs_own_state/tech.py#L41-L52) checks the device names in order on [line 44](../src/l8_2_subgraphs_own_state/tech.py#L44). `next(..., None)` returns the first match, or `None` when there is none. The `interrupt()` on [line 51](../src/l8_2_subgraphs_own_state/tech.py#L51) works as it did in [lesson 6.1](../../../6-human-in-the-loop/6.1-interrupt-and-resume/docs/readalong.md). The first time it runs, it stops the run and hands its question up. On resume, it returns the resume value, and that value becomes `device` with no check. Experiment 5 shows what an unknown answer does. The validation loop from [lesson 6.2](../../../6-human-in-the-loop/6.2-interrupt-patterns/docs/notes.md#validate-ask-again-until-the-answer-makes-sense) is how you would guard it.
- [`suggest_fix`](../src/l8_2_subgraphs_own_state/tech.py#L55-L57) looks up the fix by plain indexing. A device that is not in `FIXES` raises `KeyError`, which is what experiment 5 shows.
- [`build_tech`](../src/l8_2_subgraphs_own_state/tech.py#L64-L75) wires `START -> identify_device -> suggest_fix -> END`. On [line 75](../src/l8_2_subgraphs_own_state/tech.py#L75) it compiles with no checkpointer, like `build_billing`. Run on its own, as in test 2, the graph has no saver, and because the router ticket names a device, the interrupt is never reached. Inside the desk, it uses the saver the desk lends it ([8.1, section 4](../../8.1-subgraphs-shared-state/docs/readalong.md#section-4-one-saver-two-namespaces-lines-70-90)). `build_tech()` takes no parameters, so lesson 8.3 can extend this file.

## [desk.py](../src/l8_2_subgraphs_own_state/desk.py)

The parent graph. It now routes to three nodes: `billing`, a compiled graph added as a node, as in 8.1; `tech`, a function that calls a compiled graph; and `general`.

- [`classify`](../src/l8_2_subgraphs_own_state/desk.py#L40-L47) checks billing words first, then tech words. The order matters only for a ticket that contains words from both lists: billing wins. `VAGUE_TECH_TICKET` goes to tech because "crashes" contains "crash", since the check is a substring test.
- [`TECH_TEAM`](../src/l8_2_subgraphs_own_state/desk.py#L72) is built once, when the module is imported. This placement does more than save work. When `build_desk` adds the function `tech` as a node, LangGraph looks for subgraphs inside it without running it: it collects the globals and closure variables the function refers to, and checks whether any of them is a compiled graph. `TECH_TEAM` is such a global, so `desk.get_subgraphs()` reports `tech` (section 2), and `get_state(..., subgraphs=True)` knows which graph to ask for the saved state (section 3). If the graph is built inside the function, the run itself still works, but the desk cannot find the subgraph, and the paused task has no subgraph state at all (experiment 3).
- [`tech`](../src/l8_2_subgraphs_own_state/desk.py#L75-L99) is the wrapper node. It has three steps, and you are responsible for all of them:
  - **Map in**, on [line 91](../src/l8_2_subgraphs_own_state/desk.py#L91): the subgraph's whole input is the dict built there, `{"problem": <ticket text>}`. If you pass `state` instead, LangGraph ignores `messages` and `category`, because `TechState` has no such channels, and `problem` is missing (experiment 2).
  - **The call**, on the same line: `TECH_TEAM.invoke(...)` gets no config. Inside a running node, LangGraph passes the current run's config on to nested runnables by itself, as the comment above the line explains. So this inner run is not a separate run. It gets its own namespace `tech:<task_id>`, saves to the desk's checkpointer, appears in `stream(subgraphs=True)`, and its interrupt pauses the whole desk.
  - **Map out**, on [lines 98-99](../src/l8_2_subgraphs_own_state/desk.py#L98-L99): `invoke` returns the subgraph's whole final state, but the desk only receives what `tech` returns. The desk applies that through its own reducers, so `add_messages` appends the one new `AIMessage`. `problem`, `device` and `fix` never reach the desk. Section 1 prints the state keys to show this. If you return `result` unchanged, no error is raised: none of its keys is a desk key, so the update is quietly lost (experiment 1).
- On resume, `tech` runs again **from its first line**. This is the replay rule from [lesson 6.3](../../../6-human-in-the-loop/6.3-rules-of-interrupts/docs/notes.md#one-mechanism-replay-with-stored-answers): a node that paused is restarted, not continued. The map-in on line 91 therefore runs twice. In this code that is harmless, but a side effect placed before the `invoke` would happen twice (experiment 4). The subgraph does not start over, though. The inner `invoke` finds its saved checkpoint under the same namespace and continues at `identify_device`, where `interrupt()` now returns the answer.
- In [`build_desk`](../src/l8_2_subgraphs_own_state/desk.py#L106-L143), [line 125](../src/l8_2_subgraphs_own_state/desk.py#L125) and [line 130](../src/l8_2_subgraphs_own_state/desk.py#L130) show the two ways next to each other. `add_node("billing", build_billing())` passes a compiled graph, and the desk hands it its state directly. `add_node("tech", tech)` passes a function, so to the desk `tech` is an ordinary node. The comment above line 130 gives the rule for choosing between them. The path map on [line 136](../src/l8_2_subgraphs_own_state/desk.py#L136) gains `"tech"`, and [line 139](../src/l8_2_subgraphs_own_state/desk.py#L139) ends the tech branch. The checkpointer still goes only to the parent, on [line 143](../src/l8_2_subgraphs_own_state/desk.py#L143).

## [show.py](../src/l8_2_subgraphs_own_state/show.py)

Unchanged; see [8.1](../../8.1-subgraphs-shared-state/docs/readalong.md#showpy). This lesson relies on one detail: [`node_path`](../src/l8_2_subgraphs_own_state/show.py#L14-L21) also reads a `checkpoint_ns` string once it is split on `"|"`. Section 3 uses that to print `tech` instead of `tech:<uuid>`.

## [\_\_main\_\_.py](../src/l8_2_subgraphs_own_state/__main__.py)

The live run. [`TECH_TICKET`](../src/l8_2_subgraphs_own_state/__main__.py#L13) names a laptop, so the tech graph runs straight through. [`VAGUE_TECH_TICKET`](../src/l8_2_subgraphs_own_state/__main__.py#L15) names no device, so the tech graph has to ask. [`main`](../src/l8_2_subgraphs_own_state/__main__.py#L18-L98) builds one `InMemorySaver` and one desk, then uses four threads, so the sections do not see each other's messages.

### Section 1: map in and out ([lines 27-36](../src/l8_2_subgraphs_own_state/__main__.py#L27-L36))

A plain `invoke` (v1 format), so `result` is the state dict. The loop prints two messages: the ticket and the reply that `tech` built. [Line 34](../src/l8_2_subgraphs_own_state/__main__.py#L34) prints `['category', 'messages']`, the desk's keys only. In 8.1, the billing subgraph's whole final state was offered to the desk, and `invoice_id` was dropped because the desk has no channel for it. Here the desk is offered only what the wrapper returns.

### Section 2: the two ways side by side ([lines 38-59](../src/l8_2_subgraphs_own_state/__main__.py#L38-L59))

[Line 42](../src/l8_2_subgraphs_own_state/__main__.py#L42) lists `['billing', 'tech']`. Billing is found because it *is* the node. Tech is found through the function's reference to `TECH_TEAM`, as described above.

The loop on [lines 48-57](../src/l8_2_subgraphs_own_state/__main__.py#L48-L57) streams one billing ticket and one tech ticket with the same arguments as in [8.1, section 3](../../8.1-subgraphs-shared-state/docs/readalong.md#section-3-streaming-from-both-levels-lines-46-68). Both subgraphs report their inner steps under their own namespace, so the inner lines look alike. The difference is in the last root line of each ticket. `billing` writes the subgraph's final `messages`, the ticket and the reply (`['human', 'billing']`), which `add_messages` deduplicates by id. `tech` writes only the one message the wrapper returned (`['tech']`).

### Section 3: a paused subgraph ([lines 61-87](../src/l8_2_subgraphs_own_state/__main__.py#L61-L87))

[Line 63](../src/l8_2_subgraphs_own_state/__main__.py#L63) uses `version="v2"`, so `out` is a `GraphOutput`, and the question raised inside the subgraph comes out in `out.interrupts` of the **parent's** call ([6.1, v2 format](../../../6-human-in-the-loop/6.1-interrupt-and-resume/docs/notes.md#the-v2-format)).

- `desk.get_state(ticket_4)` on [line 67](../src/l8_2_subgraphs_own_state/__main__.py#L67) is the parent's snapshot. `next` is `('tech',)`: the parent is waiting in front of its `tech` node, and the parent does not know or care that the pause happened one level down. `tasks` has one entry per pending node.
- On [line 72](../src/l8_2_subgraphs_own_state/__main__.py#L72), without `subgraphs=True`, that task's `state` is only a config with `thread_id` and `checkpoint_ns`. It points at where the subgraph's checkpoints are stored, but it does not load them. The run prints only the key names, because the namespace contains a task id that changes on every run.
- On [line 81](../src/l8_2_subgraphs_own_state/__main__.py#L81), with `subgraphs=True`, LangGraph follows that pointer. For each pending task whose node is one of the desk's known subgraphs, it calls the subgraph's own `get_state`, and places the resulting `StateSnapshot` in `tasks[0].state`. That snapshot holds `TechState` values: only `problem`, because `device` is what the subgraph is waiting for. Its `next` is `('identify_device',)`, the node that will run again.
- [Line 83](../src/l8_2_subgraphs_own_state/__main__.py#L83) reads the snapshot's own `checkpoint_ns` and turns it into `tech` with `node_path`, so the printout names the graph without printing the uuid.
- This view only exists while something is pending. Section 4 shows that a finished thread has no tasks. It also needs the desk's checkpointer, and a subgraph that LangGraph can find statically: with `build_tech()` inside the node, `tasks[0].state` is `None` (experiment 3).

### Section 4: resume ([lines 89-99](../src/l8_2_subgraphs_own_state/__main__.py#L89-L99))

`Command(resume="phone")` on [line 95](../src/l8_2_subgraphs_own_state/__main__.py#L95) is sent to the same thread, as in [lesson 6.1](../../../6-human-in-the-loop/6.1-interrupt-and-resume/docs/notes.md#pause-and-resume-step-by-step). The desk re-runs `tech`, and the inner `invoke` continues the saved subgraph. `interrupt()` returns `"phone"`, `suggest_fix` runs, and the wrapper maps the result out as in section 1. The loop prints the finished conversation from `out.value`. [Line 98](../src/l8_2_subgraphs_own_state/__main__.py#L98) prints `pending tasks: 0`: with nothing pending, `get_state(subgraphs=True)` has no subgraph state to show. The resume value must be a real answer: `Command(resume=None)` does not resume, as the comment on lines 91-94 notes.

## [test_own_state.py](../tests/test_own_state.py)

The tests check the facts of the run on fresh desks, and compare no raw ids. [`stream_updates`](../tests/test_own_state.py#L19-L29) is section 2's stream call, collected into a list.

- [`test_tech_node_maps_state_in_and_out`](../tests/test_own_state.py#L32-L43) checks section 1: the two messages, `category == "tech"` and the desk's two keys only.
- [`test_tech_graph_works_on_its_own`](../tests/test_own_state.py#L46-L55) invokes `build_tech()` with no desk at all and compares its whole final state. That is the independence `TechState` buys you. It also calls `classify` directly for all four tickets.
- [`test_both_ways_stream_but_write_different_updates`](../tests/test_own_state.py#L58-L75) checks `get_subgraphs()`, the order of the `(path, node)` pairs, that every tech part's namespace starts with `tech:`, and the two different root updates.
- [`test_paused_subgraph_state_is_readable`](../tests/test_own_state.py#L78-L95) checks section 3. The pointer config is a `dict` whose namespace reads `tech`, and with `subgraphs=True` the state is a `StateSnapshot` with the expected values and `next`.
- [`test_resume_finishes_ticket_and_leaves_nothing_pending`](../tests/test_own_state.py#L98-L114) checks section 4, then counts the namespaces in the saver on [lines 111-114](../tests/test_own_state.py#L111-L114). There are exactly two: the root and one `tech` namespace. Both the paused part and the resumed part of the tech run were saved in that one namespace, so the resumed subgraph continued its own history instead of starting a separate one.

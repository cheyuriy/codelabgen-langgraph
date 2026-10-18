# 8.3 Handoffs Between Agents with Command.PARENT — code walkthrough

The support desk from 8.2 has a keyword classifier that sometimes picks the wrong team. Now the billing and tech teams can fix that themselves: a node inside a team's subgraph hands the ticket to the other team, one level up, with `Command(graph=Command.PARENT, ...)`. The run sends one ticket each way on the same thread, prints what the desk kept, and shows what a handoff looks like when a team runs without a parent. Run it with `./run.sh 8.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 8.2

[show.py](../src/l8_3_agent_handoffs/show.py) is unchanged, and so are the parts of billing, tech and the desk that are not listed here. For those parts, read the [8.2 walkthrough](../../8.2-subgraphs-own-state/docs/readalong.md).

- New file [handoff.py](../src/l8_3_agent_handoffs/handoff.py): [`hand_off`](../src/l8_3_agent_handoffs/handoff.py#L13-L45) builds the handoff command, and [`ticket_text`](../src/l8_3_agent_handoffs/handoff.py#L52-L57) finds the ticket among the messages.
- [billing.py](../src/l8_3_agent_handoffs/billing.py): the constant [`TECH_WORDS`](../src/l8_3_agent_handoffs/billing.py#L17), and [`find_invoice`](../src/l8_3_agent_handoffs/billing.py#L37-L52) now reads the ticket with `ticket_text` and can hand off to tech.
- [tech.py](../src/l8_3_agent_handoffs/tech.py): [`identify_device`](../src/l8_3_agent_handoffs/tech.py#L44-L63) first hands invoice tickets to billing ([lines 46-53](../src/l8_3_agent_handoffs/tech.py#L46-L53)). The rest of it is the 8.2 code.
- [desk.py](../src/l8_3_agent_handoffs/desk.py): the new key [`handoffs`](../src/l8_3_agent_handoffs/desk.py#L45) with an `operator.add` reducer, the map-in of the [`tech`](../src/l8_3_agent_handoffs/desk.py#L105) node uses `ticket_text`, and there are new comments in `tech` and `build_desk`. There are no new nodes or edges.
- [\_\_main\_\_.py](../src/l8_3_agent_handoffs/__main__.py) is rewritten: two new tickets, the helper `stream_ticket` and four new sections. The 8.2 run is still in lesson 8.2.
- [test_handoffs.py](../tests/test_handoffs.py) replaces the 8.2 tests.

## [handoff.py](../src/l8_3_agent_handoffs/handoff.py)

The two functions that both teams share. The file sits beside the teams, not in the desk, so that it can be imported without a circular import: `desk.py` imports the teams, and the teams import this file.

- [`hand_off`](../src/l8_3_agent_handoffs/handoff.py#L13-L45) returns a `Command`, as in [lesson 3.3](../../../3-control-flow/3.3-command/docs/readalong.md). It does not run anything by itself. The node that returns it decides when the handoff happens. The new part is [line 27](../src/l8_3_agent_handoffs/handoff.py#L27). `Command.PARENT` is just the string `"__parent__"`. LangGraph checks for it when it looks at a node's return value. A normal `Command` is handled by the graph the node runs in. A `Command.PARENT` is raised as an exception, `ParentCommand`, which leaves the subgraph.
- `ParentCommand` is a `GraphBubbleUp`, the same family as the exception an `interrupt()` raises. Because of that, the subgraph's retry logic does not treat it as a failure. It puts the parent's namespace into the command and raises it again. The desk's task for the team node catches it and uses `goto` and `update` as that node's result. This is why only desk keys in the update take effect (other keys are not an error, just not applied), and why `goto` on [line 28](../src/l8_3_agent_handoffs/handoff.py#L28) must name a desk node.
- The note on [line 16](../src/l8_3_agent_handoffs/handoff.py#L16) gets `name=source`. `label` in `show.py` prints the name, so in sections 1 and 3 the note is signed `billing` or `tech`, not `ai`.
- The update on [lines 40-44](../src/l8_3_agent_handoffs/handoff.py#L40-L44) writes three keys, and each one is merged in a different way: `messages` is appended by `add_messages`, `handoffs` by `operator.add`, and `category` is simply overwritten. `"handoffs"` is a list with one entry, not a string. `operator.add` joins lists, so a plain string would fail when it is added to the list.
- [`ticket_text`](../src/l8_3_agent_handoffs/handoff.py#L52-L57) searches from the end for the first message whose `type` is `"human"`. On a thread with several tickets, as in the run, that is the latest ticket. If there were no human message, `next` without a default would raise `StopIteration`. That cannot happen here, because every run starts with a `HumanMessage`.

## [billing.py](../src/l8_3_agent_handoffs/billing.py)

The billing team. It is still added to the desk as a node (8.1), and now it can also hand a ticket off.

- [`TECH_WORDS`](../src/l8_3_agent_handoffs/billing.py#L17) is shorter than the desk's `TECH_KEYWORDS`. It has no `"login"` and no `"down"`. That is fine: billing only needs to recognise the problems it should pass on.
- In [`find_invoice`](../src/l8_3_agent_handoffs/billing.py#L37-L52), the condition on [line 44](../src/l8_3_agent_handoffs/billing.py#L44) needs both parts. A ticket hands off only when it has no invoice number **and** has a tech word. A ticket that names an invoice stays with billing even if it also says "error". A ticket with neither still gets the 8.2 answer, with `"unknown"`.
- The return type `dict | Command` only documents the two possible results. LangGraph checks the actual value at run time.
- When [lines 49-51](../src/l8_3_agent_handoffs/billing.py#L49-L51) return the handoff, the subgraph stops at that point. `find_invoice` writes no update in the subgraph, `draft_reply` is never scheduled, and the static edge `find_invoice -> draft_reply` never fires. Experiment 1 shows the other case. Without `Command.PARENT` the command goes to billing's own graph, and the edge runs `draft_reply` with no `invoice_id`.
- [`draft_reply`](../src/l8_3_agent_handoffs/billing.py#L55-L59) and [`build_billing`](../src/l8_3_agent_handoffs/billing.py#L66-L79) are unchanged. The graph contains nothing about handoffs. The new route exists only in the value a node returns.

## [tech.py](../src/l8_3_agent_handoffs/tech.py)

The tech team. Its state still has none of the desk's keys, and it is still called from inside a desk node (8.2).

- [`identify_device`](../src/l8_3_agent_handoffs/tech.py#L44-L63) searches `problem` on [line 46](../src/l8_3_agent_handoffs/tech.py#L46) with the same regex as billing. `problem` already holds the ticket text, because the desk built it with `ticket_text`, so tech does not need that function. That is why [line 10](../src/l8_3_agent_handoffs/tech.py#L10) imports only `hand_off`.
- [Line 53](../src/l8_3_agent_handoffs/tech.py#L53) writes `messages`, `category` and `handoffs` from a graph whose `TechState` has none of them. If they were returned normally, or in a `Command` without `graph=`, the tech graph would drop them without an error, because it has no channels for them (experiment 1 shows the same for billing). With `Command.PARENT`, the subgraph never reads the update. Only the desk applies it, with the desk's schema.
- The order matters. The handoff check runs before the device lookup on [lines 54-62](../src/l8_3_agent_handoffs/tech.py#L54-L62). An invoice ticket therefore leaves before `interrupt()` could pause it. `VAGUE_TECH_TICKET` names no invoice, so it still pauses exactly as in 8.2 (the last test checks this).

## [desk.py](../src/l8_3_agent_handoffs/desk.py)

The parent graph. It does not get a node or an edge for handoffs. It gets a key with a reducer, and it learns to find the ticket after a handoff.

- [`handoffs`](../src/l8_3_agent_handoffs/desk.py#L45) is the only state change. Because it is `Annotated` with `operator.add`, LangGraph keeps it in a channel that starts as an empty list. That is why `result["handoffs"]` is `[]` on tickets that never moved (test 4), even though no node wrote it. Updates from both levels go through this one channel. `hand_off` runs inside the subgraphs, but its update is still applied here, in the desk's channel.
- [`classify`](../src/l8_3_agent_handoffs/desk.py#L52-L59) still reads `messages[-1]` on [line 54](../src/l8_3_agent_handoffs/desk.py#L54). It runs right after the new ticket arrives, so the last message is the ticket. `route_ticket` runs only once, after `classify`. When a handoff changes `category` later, nothing routes on it again. The `goto` alone moves the ticket, and `category` is just a record.
- In [`tech`](../src/l8_3_agent_handoffs/desk.py#L87-L118), [line 105](../src/l8_3_agent_handoffs/desk.py#L105) is the map-in with `ticket_text`. When the tech subgraph hands off, `ParentCommand` comes out of `TECH_TEAM.invoke` as an ordinary Python exception. That has a practical consequence: a `try/except Exception` around this call would catch the handoff and lose it, because `ParentCommand` is an `Exception` subclass. Let it pass through. The map-out on [lines 117-118](../src/l8_3_agent_handoffs/desk.py#L117-L118) runs only when tech answers by itself.
- In [`build_desk`](../src/l8_3_agent_handoffs/desk.py#L125-L167) the wiring is the same as in 8.2. The comment on [lines 157-161](../src/l8_3_agent_handoffs/desk.py#L157-L161) explains what happens at run time. When billing hands off, the desk schedules two things: `tech`, because of the `goto`, and `END`, because of the static edge on [line 162](../src/l8_3_agent_handoffs/desk.py#L162). `END` stops nothing, so `tech` runs in the next step and ends through [line 163](../src/l8_3_agent_handoffs/desk.py#L163). If a handoff target also ended at another node with an edge, both would run. For that reason the docs advise against mixing `goto` and edges when you route.

## [\_\_main\_\_.py](../src/l8_3_agent_handoffs/__main__.py)

The live run. [`BILLING_TO_TECH_TICKET`](../src/l8_3_agent_handoffs/__main__.py#L20) and [`TECH_TO_BILLING_TICKET`](../src/l8_3_agent_handoffs/__main__.py#L22) are written so that the classifier is wrong on both. [`main`](../src/l8_3_agent_handoffs/__main__.py#L44-L96) builds one desk with an `InMemorySaver` and uses one thread, `customer`, on [line 48](../src/l8_3_agent_handoffs/__main__.py#L48). The second ticket therefore sees the first ticket's messages and handoff.

[`stream_ticket`](../src/l8_3_agent_handoffs/__main__.py#L26-L38) is the 8.2 stream call made into a function: `stream_mode="updates"`, `subgraphs=True`, `version="v2"`. Every line it prints is one node's update, with the node's namespace shown as `(root)`, `billing` or `tech`.

### Section 1: billing hands a ticket to tech ([lines 50-58](../src/l8_3_agent_handoffs/__main__.py#L50-L58))

Compare the output with the billing ticket in 8.2. There, the stream showed `billing find_invoice`, `billing draft_reply`, then the root `billing` line with `['human', 'billing']`, the subgraph's final messages. Here the first two lines are missing. The root `billing` line holds the three keys of the handoff's update. This is the "as if that node had returned it" from `hand_off`: to the stream, the handoff is the update of the desk node `billing`. The next three lines are the 8.2 tech flow. `phone` is found in the ticket, so there is no pause.

### Section 2: tech hands the ticket back ([lines 60-68](../src/l8_3_agent_handoffs/__main__.py#L60-L68))

The same mechanism from the other kind of subgraph. The root `tech` line has the handoff's three keys, not `['tech']` as in 8.2, because the map-out never ran. Then billing runs as a node. It receives the desk's whole `messages` list, which on this thread includes the first ticket, and it writes its whole final list back. That is why the last root `billing` line lists six labels. `add_messages` matches the five old ones by id, so only the reply is new. `find_invoice` prints `INV-2077` because `ticket_text` skipped tech's note, which deliberately does not repeat the number (experiment 3).

### Section 3: what the desk kept ([lines 70-81](../src/l8_3_agent_handoffs/__main__.py#L70-L81))

`desk.get_state(customer).values` on [line 72](../src/l8_3_agent_handoffs/__main__.py#L72) is the thread's latest checkpoint. It contains six messages: each ticket, its handoff note and its reply. [Line 78](../src/l8_3_agent_handoffs/__main__.py#L78) shows both handoff entries, one per ticket, because the reducer appended the second one. [Line 79](../src/l8_3_agent_handoffs/__main__.py#L79) shows `billing`, the value of the last write. Experiment 2 removes the reducer, and then only `['tech -> billing']` is left.

### Section 4: a team on its own ([lines 83-96](../src/l8_3_agent_handoffs/__main__.py#L83-L96))

[Line 91](../src/l8_3_agent_handoffs/__main__.py#L91) runs billing as a top-level graph. The handoff is raised as in section 1, but no parent catches it, so `invoke` raises `ParentCommand`, caught on [line 92](../src/l8_3_agent_handoffs/__main__.py#L92). `exc.args[0]` on [line 93](../src/l8_3_agent_handoffs/__main__.py#L93) is the `Command` that `hand_off` built. [Line 95](../src/l8_3_agent_handoffs/__main__.py#L95) prints only `goto` and the update's keys. It does not print `command.graph`, because LangGraph has already replaced `"__parent__"` with a namespace (here an empty string), so it no longer shows what `hand_off` wrote.

## [test_handoffs.py](../tests/test_handoffs.py)

The tests check the run's facts on fresh desks. [`ask`](../tests/test_handoffs.py#L33-L36) builds a new desk for every call, so each test thread starts empty.

- [`test_billing_hands_a_ticket_to_tech`](../tests/test_handoffs.py#L39-L48) and [`test_tech_hands_a_ticket_to_billing`](../tests/test_handoffs.py#L51-L63) check the final messages, `category` and `handoffs` for each direction. [Lines 62-63](../tests/test_handoffs.py#L62-L63) call `classify` directly to show that the classifier is still wrong, so the correct answer comes from the handoff.
- [`test_handing_off_node_writes_nothing_in_its_subgraph`](../tests/test_handoffs.py#L66-L92) checks section 1's stream: the `(path, node)` order without `find_invoice`, and the root `billing` update.
- [`test_reducer_keeps_every_handoff_on_a_thread`](../tests/test_handoffs.py#L95-L113) checks section 3 on one thread, then the three 8.2 tickets, which end with an empty log and their old replies.
- [`test_command_parent_needs_a_parent`](../tests/test_handoffs.py#L116-L132) checks the `Command` from `hand_off` directly, then section 4 for both teams. It does not check `graph` after the exception, for the reason given in section 4.
- [`test_the_8_2_pause_still_works`](../tests/test_handoffs.py#L135-L143) checks that the new check in `identify_device` left the 8.2 interrupt and resume path working.

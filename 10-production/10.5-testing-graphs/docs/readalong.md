# 10.5 Testing Graphs with pytest — code walkthrough

This lesson has no program of its own: the lesson code is the test suite. `graph.py` is a small ticket router, and the three test files test it at three levels: one node at a time, the whole graph, and only a slice of it. Run the tests with `./run.sh test 10.5` from the course root, or with `python -m pytest -v tests` inside the lesson package. Everything is offline and the suite takes well under a second.
The concept itself is explained in the [notes](notes.md).

## [graph.py](../src/l10_5_testing_graphs/graph.py)

The graph under test. It has the shape you know from lessons 1.2 and 1.3. Two choices in it exist only so that it can be tested: the chat model is a parameter, and the graph is built by a factory.

- [`BILLING_KEYWORDS` and `TECH_KEYWORDS`](../src/l10_5_testing_graphs/graph.py#L20-L21) are plain tuples, so `classify` needs no model and gives the same answer every time. That makes it the easiest node to test.
- [`SYSTEM_PROMPT`](../src/l10_5_testing_graphs/graph.py#L24) puts the team name into the prompt. The tests read the prompt the fake model received and use it to see which queue node ran before `draft_reply`.
- [`TicketState`](../src/l10_5_testing_graphs/graph.py#L30-L37) has no reducers, so each key is simply replaced by the node that writes it. Each key has one owner, and this is what makes node tests short: a node returns only its own key, and the test compares that small dict.
- [`classify`](../src/l10_5_testing_graphs/graph.py#L44-L51) reads only `text`. The billing check in line 47 comes before the tech check in line 49, so a ticket that matches both lists counts as billing. One test case checks exactly this order.
- [`route_ticket`](../src/l10_5_testing_graphs/graph.py#L58-L60) is not a node. LangGraph calls it after `classify` and uses its return value to pick the next node. The tests never call it directly. They check its effect: which queue node ran, or which node `get_state(config).next` shows.
- [`billing_queue`, `tech_queue`, `general_queue`](../src/l10_5_testing_graphs/graph.py#L67-L79) each set only `team`. The value differs per queue, so a test can tell from the result which branch ran.
- [`make_draft_reply`](../src/l10_5_testing_graphs/graph.py#L86-L103) is the only part that talks to an LLM. The inner function [`draft_reply`](../src/l10_5_testing_graphs/graph.py#L93-L101) uses the `model` from the enclosing function, so the node itself keeps the usual one-argument signature that LangGraph expects. The call `model.invoke([...])` in lines 95-100 is the standard `BaseChatModel` interface, so a real model and the fake one from `conftest.py` work the same way here. Line 101 stores only `response.content`, the reply text, not the whole `AIMessage`.
- [`send_reply`](../src/l10_5_testing_graphs/graph.py#L110-L116) stands in for a side effect. In `test_partial.py` it is the node the run must stop in front of.
- [`build_graph`](../src/l10_5_testing_graphs/graph.py#L123-L156) builds a new graph on every call. Because `model` and `checkpointer` are arguments, each test chooses its own and no state lives at module level. Line 136 is where the model gets in: `make_draft_reply(model)` creates the node function for this graph. The mapping in lines 144-148 turns the category from `route_ticket` into a node name, and it also tells LangGraph which nodes the conditional edge can lead to. The three `add_edge` calls in lines 151-153 join the branches again at `draft_reply`. Line 156 passes `checkpointer` to `compile`. With `None`, the default, the graph saves nothing, which is enough for node tests.

## [conftest.py](../tests/conftest.py)

pytest loads this file before the tests in the same folder, and every test can ask for its fixtures by naming them as parameters.

- [`RecordingChatModel`](../tests/conftest.py#L17-L37) extends `GenericFakeChatModel` from `langchain_core`. The parent class takes an iterator of `AIMessage` objects and returns the next one on every call, whatever the prompt is. The subclass adds what the parent does not offer: a record of the prompts.
- The field [`prompts`](../tests/conftest.py#L26) is a pydantic field, because chat models in `langchain_core` are pydantic models. Pydantic needs the type annotation to treat `prompts` as a field at all: an unannotated `prompts = []` on this subclass is rejected with `PydanticUserError` when the class is defined. `Field(default_factory=list)` is the explicit way to say that each model starts with a new, empty list. Pydantic would also copy an annotated `= []` default per instance, but the factory form makes the intent clear and works the same outside pydantic, where a dataclass rejects `= []` and a plain class would share one list.
- [`_generate`](../tests/conftest.py#L28-L37) is the method `BaseChatModel.invoke` calls in the end, after it has turned the input into a list of messages and set up callbacks. Overriding it here records exactly the messages the node built. Line 37 then hands over to the parent class, which takes the next scripted reply.
- [`make_model`](../tests/conftest.py#L48-L57) returns a factory and not a model, so the test decides how many replies to script. The script in line 55 is an iterator: each model call uses up one reply. When the script is empty, the next call raises `StopIteration` inside the model, and the run fails with `RuntimeError: generator raised StopIteration`. A test with too few replies therefore fails loudly.
- [`checkpointer`](../tests/conftest.py#L60-L63) returns a new `InMemorySaver` for each test, because the fixture has the default function scope. With `scope="session"` all tests would share one saver, and checkpoints from one test would show up in another.
- [`config`](../tests/conftest.py#L66-L71) gives the `thread_id` that a checkpointed graph requires for `invoke`, `stream`, `update_state` and `get_state`. All tests use the same `"ticket-1"`. This is safe only because each test has its own checkpointer.

## [test_nodes.py](../tests/test_nodes.py)

Level 1: one node, without the rest of the graph. The compiled graph's `nodes` attribute maps each node name, plus the internal `"__start__"`, to a `PregelNode`. `PregelNode.invoke(state)` runs only that node's function and returns its update. It does not merge the update into a state and does not follow any edges.

- [`test_classify_node`](../tests/test_nodes.py#L13-L31) runs four parametrized cases. The `id=` values in lines 16-19 become the test names in `pytest -v` output, for example `test_classify_node[billing-before-tech]`. Line 26 builds the graph with `make_model()` and no replies, so any model call would fail. A passing test also proves that `classify` never touches the model. Line 28 passes only `text`, because `classify` reads nothing else. Line 31 compares with `==`, so an extra key in the update would also fail the test.
- [`test_draft_reply_node`](../tests/test_nodes.py#L38-L54) passes the node the two keys it reads, `text` and `team`, in lines 44-46, as if a queue node had just run. Lines 49-52 read `model.prompts[0]`, the first and only prompt, and check both messages: the system prompt with the team name and the ticket text. Line 54 shows something you might not expect. The graph has a checkpointer, but calling a node directly goes around the Pregel loop that writes checkpoints, so `checkpointer.list(None)` (all threads) is empty.

## [test_end_to_end.py](../tests/test_end_to_end.py)

Level 2: the whole graph from START to END, with a real checkpointer and a fake model.

- [`test_full_run`](../tests/test_end_to_end.py#L10-L61) runs one case per route. Line 47 scripts exactly one reply, because a run calls the model once, in `draft_reply`. `invoke` in line 50 returns the final state values, so the comparison in lines 52-58 checks every node's key at once. Line 59 makes sure the model was called once, not more. Line 61 reads the last checkpoint: `next == ()` means nothing is left to run on the thread, so the run reached END and did not stop on the way.
- [`test_route_order`](../tests/test_end_to_end.py#L68-L76) checks the path, not the result. With `stream_mode="updates"`, `stream` yields one `{node_name: update}` dict per finished node. The comment in line 72 says "per step", which comes to the same thing in this linear graph, where each step runs one node; when nodes run in parallel in one step, each of them yields its own chunk. Line 74 keeps only the names. The expected list in line 76 shows that only one queue node ran and that the nodes ran in the order of the edges. `stream` returns a generator, and the nodes run only as line 74 reads it.

## [test_partial.py](../tests/test_partial.py)

Level 3: only a slice of the graph. The test starts after `classify` and stops before `send_reply`. More on this technique in the [notes](notes.md).

- [`test_partial_run`](../tests/test_partial.py#L16-L40):
  - Lines 24-28 seed the thread. `update_state(..., as_node="classify")` saves the values as a checkpoint written by `classify`. LangGraph then evaluates `classify`'s outgoing edges, here `route_ticket`, to decide what comes next, so the thread now waits at `tech_queue`. Without `as_node`, an update on a new thread counts as input, and the run would start at `classify` again.
  - The seed says `"refund"` but `"tech"`. If `classify` ran, it would pick billing. The Tech team in line 34 therefore shows that the seeded state decided the route.
  - Line 32 passes `None` as input, which tells LangGraph to continue the saved thread. A new input dict would start a new run at START. `interrupt_after=["draft_reply"]` pauses the run after that node and saves the checkpoint. `invoke` then returns the state so far, so `status` is missing (line 36).
  - Line 39 checks where the run stopped. LangGraph does not reject unknown names in `interrupt_after`: a typo like `"draft"` lets the run go on to END. This assertion is the one that catches it.
- [`test_resume_after_partial`](../tests/test_partial.py#L47-L66) repeats the same seed and partial run (lines 53-58), then continues with `stream(None, ...)` in line 61. The only update is from `send_reply` (line 63): the run starts from the saved checkpoint and does not repeat the nodes that already finished. The model has a single scripted reply and line 65 still counts one prompt, so the saved draft is reused and not generated again.

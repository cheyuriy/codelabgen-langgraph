# 5.1 Checkpointers and Threads — code walkthrough

The program takes the calculator agent from lesson 4.2 and compiles it with an `InMemorySaver`. Then the agent remembers earlier turns in one thread (`chat-1`) and starts fresh in another (`chat-2`). It streams the first turn one checkpoint at a time, runs a follow-up in both threads, and prints what `get_state` returns. Run it with `./run.sh 5.1` from the course root.
The concept itself is explained in the [notes](notes.md).

## Where the code comes from

This is the first lesson of module 5, and its example is new. It is a compact copy of the [4.2 agent](../../../4-agents/4.2-tool-calling-loop/docs/readalong.md), so a diff against 4.2 shows only the new idea:

- [tools.py](../src/l5_1_checkpointers_and_threads/tools.py) is copied unchanged.
- [chatbot.py](../src/l5_1_checkpointers_and_threads/chatbot.py) keeps the fake model and the graph wiring. 4.2's pairing check (`unanswered_tool_calls`) is gone. [`build_graph`](../src/l5_1_checkpointers_and_threads/chatbot.py#L85-L130) takes a second argument, `checkpointer`, and passes it to `compile` on [line 130](../src/l5_1_checkpointers_and_threads/chatbot.py#L130).
- [\_\_main\_\_.py](../src/l5_1_checkpointers_and_threads/__main__.py) and [test_checkpointer.py](../tests/test_checkpointer.py) are new. Only the `describe` helper is the same as in 4.2.
- [pyproject.toml](../pyproject.toml#L8) also pins `langgraph-checkpoint==4.3.0`, because `__main__.py` imports `InMemorySaver` from it directly. It is the version `langgraph` 1.2.16 installs anyway.

## [tools.py](../src/l5_1_checkpointers_and_threads/tools.py)

The three tools the agent can call. Nothing here knows about persistence.

- [`add`](../src/l5_1_checkpointers_and_threads/tools.py#L11-L19), [`multiply`](../src/l5_1_checkpointers_and_threads/tools.py#L22-L30) and [`divide`](../src/l5_1_checkpointers_and_threads/tools.py#L33-L41) are `@tool` functions. The docstring becomes the description the model reads, and the type hints become the argument schema.
- `divide` on [line 41](../src/l5_1_checkpointers_and_threads/tools.py#L41) has no zero check on purpose. One test and one experiment divide by zero to show what a checkpointer keeps after a crash.
- [`TOOLS`](../src/l5_1_checkpointers_and_threads/tools.py#L45) is the one list given both to the model and to `ToolNode`.

## [chatbot.py](../src/l5_1_checkpointers_and_threads/chatbot.py)

The model, and the graph that is compiled with a checkpointer.

- [Line 18](../src/l5_1_checkpointers_and_threads/chatbot.py#L18) imports `BaseCheckpointSaver` only for the type hint. It is the base class (the saver interface) with `get_tuple`, `list`, `put` and `put_writes`. `InMemorySaver`, and later `SqliteSaver` and `PostgresSaver`, implement it. So `build_graph` works with any saver, and 5.2 changes only the line that creates it.
- [`SYSTEM_PROMPT`](../src/l5_1_checkpointers_and_threads/chatbot.py#L31) is added to every model call and never stored in state. So it is not in any checkpoint either: a checkpoint holds only state channels.
- [`ToolCallingFakeModel`](../src/l5_1_checkpointers_and_threads/chatbot.py#L36-L47) is the scripted model from 4.2. `bind_tools` returns the model itself, because the scripted replies already say which tools to call.
- [`make_model`](../src/l5_1_checkpointers_and_threads/chatbot.py#L50-L68) has one new sentence in its docstring, [lines 58-60](../src/l5_1_checkpointers_and_threads/chatbot.py#L58-L60). It matters more now: the graph is built once and invoked several times, and every invoke takes its replies from the same iterator. So the script must hold the replies of all turns and all threads, in the order the model is called. If it runs out, the run fails with `RuntimeError: generator raised StopIteration`.
- [`tool_call`](../src/l5_1_checkpointers_and_threads/chatbot.py#L71-L78) builds a reply that asks for one tool, the way a real model does.
- [`build_graph`](../src/l5_1_checkpointers_and_threads/chatbot.py#L85-L130): the signature on [line 86](../src/l5_1_checkpointers_and_threads/chatbot.py#L86) has no default for `checkpointer`. A caller has to decide about persistence, and `None` means "no persistence", as in 4.2.
  - [`call_model`](../src/l5_1_checkpointers_and_threads/chatbot.py#L102-L108) is unchanged, but what it sees has changed. `state["messages"]` on [line 105](../src/l5_1_checkpointers_and_threads/chatbot.py#L105) now holds the whole thread, earlier turns included, because the graph loads the saved state before it runs. The node itself doesn't know a checkpointer exists.
  - The wiring on [lines 113-124](../src/l5_1_checkpointers_and_threads/chatbot.py#L113-L124) is 4.2's loop: `call_model`, then `tools` while the reply has tool calls, then back to `call_model`. Each node run is one super-step, and after each super-step the checkpointer saves a checkpoint.
  - [Line 130](../src/l5_1_checkpointers_and_threads/chatbot.py#L130) is the only real change. `compile(checkpointer=...)` stores the saver in the compiled graph. From then on, every `invoke`, `stream` and `get_state` needs a `thread_id` in `config["configurable"]`. A run first loads that thread's latest checkpoint, merges its input into it through the reducers (`add_messages` here), and saves new checkpoints as it goes. The graph object itself keeps no conversation data: all of it is in the saver.

## [\_\_main\_\_.py](../src/l5_1_checkpointers_and_threads/__main__.py)

The live run: one graph, one saver, two threads, and the saved state at the end.

- [Line 8](../src/l5_1_checkpointers_and_threads/__main__.py#L8) imports `InMemorySaver`. `MemorySaver` is the same class under an old name; the lesson uses the current one.
- [`describe`](../src/l5_1_checkpointers_and_threads/__main__.py#L13-L23) prints a message on one line without its id, so the output is the same in every run. It is the same helper as in 4.2.
- [`main`](../src/l5_1_checkpointers_and_threads/__main__.py#L26-L127) sets everything up before the four sections:
  - [Line 30](../src/l5_1_checkpointers_and_threads/__main__.py#L30) creates the saver once for the whole process. `InMemorySaver` keeps its checkpoints in a nested dict inside this object, keyed by thread_id, then checkpoint namespace, then checkpoint id. A second `InMemorySaver()` would be a separate, empty store (one of the experiments).
  - The [`script`](../src/l5_1_checkpointers_and_threads/__main__.py#L34-L43) holds five replies: two for turn 1, two for turn 2 and one for `chat-2`, in the order the model is called.
  - [Line 44](../src/l5_1_checkpointers_and_threads/__main__.py#L44) builds the graph with the saver. This is the line 5.2 changes.
  - [Lines 48-49](../src/l5_1_checkpointers_and_threads/__main__.py#L48-L49) are the two configs. The thread_id is any string you choose, for example a user or chat id. The graph doesn't create threads: a thread exists as soon as the first checkpoint is saved under its id.

### Section `checkpoint_stream`, [lines 51-73](../src/l5_1_checkpointers_and_threads/__main__.py#L51-L73)

- The call on [lines 61-63](../src/l5_1_checkpointers_and_threads/__main__.py#L61-L63) runs turn 1 with `stream_mode="checkpoints"`. Each event is one saved checkpoint, as a dict with the keys of a `StateSnapshot` (`values`, `next`, `config`, `metadata`, …).
- [Lines 64-67](../src/l5_1_checkpointers_and_threads/__main__.py#L64-L67) print three things per checkpoint: `metadata["step"]`, `metadata["source"]` and the message count in `values`, plus `next`, the nodes that will run from that checkpoint. In the output:
  - step -1, `input`: the input is saved but not applied yet. `values` has no messages, and `next` is `['__start__']`.
  - step 0, `loop`: the `__start__` step wrote the question into `messages`; `call_model` runs next.
  - steps 1-3, `loop`: one checkpoint after each node run (`call_model`, `tools`, `call_model`). The last one has `next=[]`: the run is over.
- `.get("messages", [])` on [line 65](../src/l5_1_checkpointers_and_threads/__main__.py#L65) is a defensive default, not a requirement: at step -1 the stream event's `values` already show `{"messages": []}`, because the `messages` channel starts as an empty list while the input still sits in the `__start__` channel.
- The `if` on [line 71](../src/l5_1_checkpointers_and_threads/__main__.py#L71) is there for the experiment that passes `None` as the checkpointer: then the stream emits no events at all, and `last` stays `None`.

### Section `same_thread`, [lines 76-86](../src/l5_1_checkpointers_and_threads/__main__.py#L76-L86)

- [Line 82](../src/l5_1_checkpointers_and_threads/__main__.py#L82) sends only the follow-up question with `chat1`. Before running, the graph loads the step 3 checkpoint of `chat-1`, so `add_messages` appends the new question to the four saved messages.
- `invoke` returns the whole state of the thread, not just the new messages. That is why the loop on [lines 83-84](../src/l5_1_checkpointers_and_threads/__main__.py#L83-L84) prints turn 1 again, and [line 85](../src/l5_1_checkpointers_and_threads/__main__.py#L85) reports 8 messages after sending 1.
- The fake model ignores its input, so the reply `multiply(a=7, b=2)` comes from the script. A real model would get the same 8-message history and could find the 7 in it.

### Section `new_thread`, [lines 89-95](../src/l5_1_checkpointers_and_threads/__main__.py#L89-L95)

- [Line 92](../src/l5_1_checkpointers_and_threads/__main__.py#L92) sends the same follow-up with `chat2`. The saver has nothing under `chat-2`, so the run starts from empty state, and the result has only 2 messages. Same graph, same saver, different key.

### Section `inspect_state`, [lines 98-128](../src/l5_1_checkpointers_and_threads/__main__.py#L98-L128)

- [Line 101](../src/l5_1_checkpointers_and_threads/__main__.py#L101): `get_state(chat1)` asks the saver for the latest checkpoint of `chat-1` and returns it as a `StateSnapshot`, a `NamedTuple` from `langgraph.types`. It runs nothing.
- [Lines 103-104](../src/l5_1_checkpointers_and_threads/__main__.py#L103-L104): `values` is the state dict, here the 8 messages.
- [Line 106](../src/l5_1_checkpointers_and_threads/__main__.py#L106): `next` is a tuple here (in the stream events it was a list). `()` means no node is waiting. After a crash, it names the node that did not finish (see the tests).
- [Lines 109-113](../src/l5_1_checkpointers_and_threads/__main__.py#L109-L113): `config["configurable"]` addresses this exact checkpoint. `thread_id` is the thread, `checkpoint_ns` is `''` for the top-level graph (subgraphs get their own namespace), and `checkpoint_id` is the id of this checkpoint. The id changes on every run, so only whether it is set is printed.
- [Line 117](../src/l5_1_checkpointers_and_threads/__main__.py#L117): `step` is 8, not 3. Steps count across the whole thread: turn 2 saved its `input` checkpoint as step 4 and its loop checkpoints as steps 5-8.
- [Line 119](../src/l5_1_checkpointers_and_threads/__main__.py#L119): `parent_config` points at the checkpoint saved just before, step 7. The checkpoints of a thread form a chain; walking it is lesson 6.5.
- [Lines 122-123](../src/l5_1_checkpointers_and_threads/__main__.py#L122-L123) call the saver directly. `checkpointer.list(config)` yields the thread's checkpoints, newest first. `chat-1` has 10 (5 per turn), `chat-2` has 3 (input, step 0, one `call_model` step).
- [Line 126](../src/l5_1_checkpointers_and_threads/__main__.py#L126): a thread that never ran is not an error. `get_state` returns an empty snapshot with `values == {}` and `next == ()`.

## [test_checkpointer.py](../tests/test_checkpointer.py)

The tests check the same behaviour without printing, plus two cases the live run doesn't show.

- [`two_turn_script`](../tests/test_checkpointer.py#L17-L24) returns fresh `AIMessage` objects on every call, because the fake model sets ids on them. [`run_two_turns`](../tests/test_checkpointer.py#L27-L33) builds a checkpointed graph and runs both `chat-1` turns.
- [`test_memory_within_a_thread`](../tests/test_checkpointer.py#L36-L49): the second invoke returns 8 messages in the order human, ai, tool, ai, human, ai, tool, ai. [Line 48](../tests/test_checkpointer.py#L48) checks that the saved state holds the same messages as the result.
- [`test_threads_are_separate`](../tests/test_checkpointer.py#L52-L63): `chat-2` gets 2 messages, `chat-1` still has 8, and the unused `chat-3` is empty.
- [`test_when_checkpoints_are_written`](../tests/test_checkpointer.py#L66-L88) pins the step, source and `next` of each turn 1 checkpoint. [Line 87](../tests/test_checkpointer.py#L87) reverses `checkpointer.list` into the order written, and [line 88](../tests/test_checkpointer.py#L88) checks that turn 2 starts with its own `input` checkpoint at step 4.
- [`test_state_snapshot_after_turn_two`](../tests/test_checkpointer.py#L91-L108): [line 104](../tests/test_checkpointer.py#L104) shows that the snapshot's `checkpoint_id` is the id of the saver's latest checkpoint (`get_tuple` without a `checkpoint_id` returns the latest one). `tasks == ()` means nothing is pending.
- [`test_failed_run_keeps_its_progress`](../tests/test_checkpointer.py#L111-L127): the model asks for `divide(1, 0)`, and `ToolNode` lets the `ZeroDivisionError` through, so `invoke` raises. The checkpoint saved after `call_model` (step 1) is still there: 2 messages, and `next == ("tools",)` says which node did not finish. The failed task is listed in `tasks` with its error. [Line 127](../tests/test_checkpointer.py#L127) compares the error with a string, `"ZeroDivisionError('division by zero')"`, not an exception: the error went through the saver's serializer, which stores an exception as its repr.
- [`test_misuse_errors`](../tests/test_checkpointer.py#L130-L138): [line 134](../tests/test_checkpointer.py#L134) invokes a checkpointed graph without a config and gets a `ValueError` naming `thread_id`. There is no default thread. [Line 138](../tests/test_checkpointer.py#L138): `get_state` on a graph compiled with `None` raises `ValueError: No checkpointer set`.

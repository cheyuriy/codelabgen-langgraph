# 5.3 Trimming and Summarizing Message History — code walkthrough

The program runs the calculator agent from 5.2 for four turns on one thread. It prints what the model actually receives on every call, what the thread saved after every turn, and finally what the thread's checkpoints still hold. The model sees only the newest messages. Once a finished turn leaves too many messages in the state, the old ones are folded into a running summary and deleted. Run it with `./run.sh 5.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 5.2

- [tools.py](../src/l5_3_message_history/tools.py) is copied from 5.2 without changes, and [pyproject.toml](../pyproject.toml#L6-L12) keeps the same five pins. `SqliteSaver` is still used, now in one process.
- [chatbot.py](../src/l5_3_message_history/chatbot.py) keeps the system prompt, the fake model and the `tools` node from 5.2 (explained in the [5.1 read-along](../../5.1-checkpointers-and-threads/docs/readalong.md)). The new parts:
  - the limits in [`history_limits`](../src/l5_3_message_history/chatbot.py#L42-L52) and a [`State`](../src/l5_3_message_history/chatbot.py#L56-L66) with an extra `summary` key;
  - [`recent_messages`](../src/l5_3_message_history/chatbot.py#L73-L96) and [`model_input`](../src/l5_3_message_history/chatbot.py#L103-L114). `call_model` now sends `model_input(state)` instead of the whole state;
  - [`route_after_model`](../src/l5_3_message_history/chatbot.py#L121-L133) replaces `tools_condition` on the edge out of `call_model`;
  - `build_graph` takes a third argument, `summarizer`, and has a new node [`summarize`](../src/l5_3_message_history/chatbot.py#L221-L259).
- [\_\_main\_\_.py](../src/l5_3_message_history/__main__.py) is rewritten. The child processes and the crash demo from 5.2 are gone. There is one process and one four-turn thread, and a [`PeekingModel`](../src/l5_3_message_history/__main__.py#L26-L54) prints each model input.
- [test_message_history.py](../tests/test_message_history.py) is new. 5.2's tests are not copied.

## [chatbot.py](../src/l5_3_message_history/chatbot.py)

The file holds the whole idea of the lesson. Read it top to bottom: limits and state, the two helpers that pick messages, the router, then the graph.

### Limits and state

- [Lines 48-50](../src/l5_3_message_history/chatbot.py#L48-L50) are the three numbers that shape the run. They are counted in messages, not tokens, because `recent_messages` uses `token_counter=len`. The numbers fit together: `KEEP_AFTER_SUMMARY` (4) is smaller than `SUMMARIZE_AFTER` (6), so a summary really shrinks the state. 4 holds a complete turn with one tool call (human, ai, tool, ai), which is every turn in the run. It is not a general guarantee: each extra tool call adds messages, so a turn with two parallel tool calls (human, ai, tool, tool, ai) or two sequential ones is longer than 4. Then the newest 4 hold no `HumanMessage`, and `summarize` has to skip (see the guard below). Size both limits for the longest turn you expect.
- [`SUMMARY_PREFIX`](../src/l5_3_message_history/chatbot.py#L51) is shared with `__main__.py`, which looks for it to mark a system message as `system+summary`, and with the tests.
- [`State`](../src/l5_3_message_history/chatbot.py#L56-L66) subclasses `MessagesState`, so `messages` keeps its `add_messages` reducer. `summary` on [line 66](../src/l5_3_message_history/chatbot.py#L66) has no reducer, so LangGraph stores it in a plain "last value" channel: each update replaces it. The channel is empty until the first summary is written, and an empty channel is left out of the state. That is why the code reads it with `state.get("summary", "")` and why turn 1's result has no `summary` key at all.

### [`recent_messages`](../src/l5_3_message_history/chatbot.py#L73-L96)

This is the only place that calls `trim_messages`. Both the model request and the summary node use it, so they follow the same rule.

- `strategy="last"` on [line 83](../src/l5_3_message_history/chatbot.py#L83) walks the list from the end and keeps messages while the count fits in `max_tokens`.
- `token_counter=len` on [line 85](../src/l5_3_message_history/chatbot.py#L85): `trim_messages` calls the counter with a list of messages, and `len` of a list is the number of messages. A real app passes `"approximate"` or the chat model here, and `max_tokens` becomes a real token budget.
- `start_on="human"` on [line 92](../src/l5_3_message_history/chatbot.py#L92) runs after the cut and drops messages from the front until the first one is a `HumanMessage`. You can see the effect in turn 2's second call: the history is `human ai tool ai human ai tool`, the newest 5 are `tool ai human ai tool`, and `start_on` cuts them back to `human ai tool`. So the model gets 3 messages although 5 were allowed. Without `start_on` it would get the orphan `tool` first, and a real provider would reject the request.
- If the window holds no `HumanMessage`, the result is an empty list. In this run that never happens, but it does whenever the window is smaller than the current turn: try `MAX_MODEL_MESSAGES = 2`, or a turn with three tool rounds, where the newest 5 of `human ai tool ai tool ai tool` start with `tool` and the model gets only the system prompt. The same empty result is what the guard in `summarize` checks for.
- The returned list holds the same message objects, not copies, and the input is not changed. `summarize` relies on the ids of the kept messages being the ones saved in state, because it compares them with the ids in state. Object identity does not matter: copies with the same ids would work too.

### [`model_input`](../src/l5_3_message_history/chatbot.py#L103-L114)

`model_input` builds the request. The summary is added to the system prompt text ([lines 110-112](../src/l5_3_message_history/chatbot.py#L110-L112)), not stored as a message. So it is never trimmed away and never counts against `MAX_MODEL_MESSAGES`. [Line 114](../src/l5_3_message_history/chatbot.py#L114) puts a fresh `SystemMessage` in front of the trimmed window. Nothing here is returned to the graph, so the saved state keeps every message. The first test checks exactly this.

### [`route_after_model`](../src/l5_3_message_history/chatbot.py#L121-L133)

- [Line 127](../src/l5_3_message_history/chatbot.py#L127) reuses `tools_condition`. It returns `"tools"` when the last message has tool calls and `"__end__"` otherwise. Only the second case is changed.
- [Line 133](../src/l5_3_message_history/chatbot.py#L133) checks the length of the saved history, not of the model's window. It runs only after a final answer, so the deleted part never cuts into a turn that is still running.
- The return annotation `Literal["tools", "summarize", "__end__"]` on [line 121](../src/l5_3_message_history/chatbot.py#L121) is read by LangGraph: `add_conditional_edges` without a path map takes the possible targets from it, for example to draw the graph. `END` is the string `"__end__"`.

### [`build_graph`](../src/l5_3_message_history/chatbot.py#L189-L285)

- The new `summarizer` argument on [line 190](../src/l5_3_message_history/chatbot.py#L190) is a separate chat model. It is never bound to tools: it only writes text.
- [Line 213](../src/l5_3_message_history/chatbot.py#L213) in `call_model` is the only change there: the model gets `model_input(state)`. The reply is still returned as a one-item list, and `add_messages` appends it to the full history.

**[`summarize`](../src/l5_3_message_history/chatbot.py#L221-L259)**

- [Line 226](../src/l5_3_message_history/chatbot.py#L226) picks `kept`. `kept` is the newest window of 4, chosen by the same `recent_messages`, and `old` is everything else. Because `kept` starts on a `HumanMessage`, `old` is a run of complete turns. In turn 2, `old` is turn 1 (4 messages). In turn 4, `old` is turns 2 and 3 (6 messages).
- [Lines 232-233](../src/l5_3_message_history/chatbot.py#L232-L233) are the guard for a turn longer than `KEEP_AFTER_SUMMARY`. With two tool calls in the last turn, the newest 4 are `ai tool tool ai`, `start_on` drops all of them, and `kept` is empty. Without the guard, `old` would be the whole list, and `summarize` would delete every message, including the answer it was just given. Returning `{}` is an update with no keys: LangGraph changes no channel, still writes the checkpoint for this step, and the turn ends with the full history and the old summary. The history stays over the threshold, so the next turn short enough to fit in 4 messages summarizes everything before it at once. The run never reaches this branch; the last test does.
- [Lines 234-235](../src/l5_3_message_history/chatbot.py#L234-L235) split the history: `old` is every message whose id is not in `kept`.
- [Lines 239-245](../src/l5_3_message_history/chatbot.py#L239-L245) choose the instruction. The first summary asks for a fresh summary. Later ones pass the old summary and ask to extend it. That is why the summarizer never needs the messages deleted earlier.
- [Line 246](../src/l5_3_message_history/chatbot.py#L246) sends `old` plus the instruction as a `HumanMessage`. This is why the run prints `summarizer gets: human ai tool ai human`: the last `human` is the instruction. The instruction and the summarizer's reply are not added to `messages`; only `reply.content` is kept, as the new `summary`.
- [Line 259](../src/l5_3_message_history/chatbot.py#L259) returns both keys in one update. `summary` replaces the old value. `messages` gets one `RemoveMessage(id=...)` per old message, and `add_messages` deletes the messages with those ids from the list instead of appending anything. Both changes land in the same super-step, so the checkpoint written after `summarize` has the smaller history and the new summary together.
- The ids exist because `add_messages` gives every message an id when it enters state. An id that is not in the list makes `add_messages` raise `ValueError` (`test_remove_message_needs_a_real_id` shows it).

**Wiring.** [Line 264](../src/l5_3_message_history/chatbot.py#L264) builds the graph from `State`, so the `summary` channel exists. [Line 270](../src/l5_3_message_history/chatbot.py#L270) adds the `summarize` node, [line 275](../src/l5_3_message_history/chatbot.py#L275) puts `route_after_model` on the edge out of `call_model`, and [line 279](../src/l5_3_message_history/chatbot.py#L279) ends the turn after a summary. `summarize` does not go back to `call_model`: the answer was already given before the summary ran.

## [\_\_main\_\_.py](../src/l5_3_message_history/__main__.py)

### [`PeekingModel`](../src/l5_3_message_history/__main__.py#L26-L54)

- `PeekingModel` subclasses the lesson's `ToolCallingFakeModel` so that it still accepts `bind_tools`. `label` on [line 36](../src/l5_3_message_history/__main__.py#L36) is a pydantic field, so it can be passed to the constructor like `messages`.
- `_generate` is the method that `BaseChatModel.invoke` calls with the final list of messages, after the graph and `model_input` have done their work. Printing there shows exactly what a real provider would receive. [Line 54](../src/l5_3_message_history/__main__.py#L54) then lets `GenericFakeChatModel._generate` return the next scripted reply, which does not depend on the input.

### [`main`](../src/l5_3_message_history/__main__.py#L60-L136)

- [Lines 63-71](../src/l5_3_message_history/__main__.py#L63-L71): one script holds the replies of all four turns in call order, because one model serves every `invoke`. Turn 3 needs only one reply because it has no tool call.
- [Lines 77-80](../src/l5_3_message_history/__main__.py#L77-L80): the summarizer is a second scripted fake with two replies, one per summary.
- [Lines 91-94](../src/l5_3_message_history/__main__.py#L91-L94) open a `SqliteSaver` on a file in a temporary directory. Both context managers close in reverse order, so the connection is closed before the directory is deleted. Deleting messages is an ordinary write for the saver.
- [Lines 95-99](../src/l5_3_message_history/__main__.py#L95-L99): the main model and the summarizer are two different objects with their own scripts, so a summary call never uses up a reply meant for the agent.

**Section [`conversation`](../src/l5_3_message_history/__main__.py#L102-L121).** Each turn sends only the new question ([line 113](../src/l5_3_message_history/__main__.py#L113)), and the checkpointer adds it to the saved thread. `result` is the whole saved state after the turn, so [lines 115-118](../src/l5_3_message_history/__main__.py#L115-L118) print what the thread keeps, not what the model saw. In the output:

- Turn 1 ends with 4 messages, not more than 6, so the route goes to `END`.
- Turn 2 reaches 8 messages, so `summarize` runs and leaves the 4 messages of turn 2.
- Turn 3 adds 2 messages (no tool call) and stops at exactly 6. The check is `>`, so there is no summary. Its model call is the first one with `system+summary`.
- Turn 4's first call gets `system+summary human ai human`: the newest 5 of 7 begin with `tool ai`, which `start_on` drops. The turn reaches 10 messages, and the summary extends the old one.

**Section [`checkpoint_history`](../src/l5_3_message_history/__main__.py#L123-L137).** `checkpointer.list(config)` on [line 130](../src/l5_3_message_history/__main__.py#L130) returns every checkpoint of the thread, newest first. `checkpoint["channel_values"]` is the raw saved state of each one. [Line 132](../src/l5_3_message_history/__main__.py#L132) uses `.get("messages", [])` because the very first checkpoint (the input, step -1) has no `messages` channel yet. The output `latest: 4 messages; most in any checkpoint: 10; checkpoints: 20` shows the point: the latest state is small, but the checkpoint written right before turn 4's summary still holds all 10 messages. Turns 1 and 3 write 5 and 3 checkpoints, turns 2 and 4 write 6 each because `summarize` is one more step.

## [test_message_history.py](../tests/test_message_history.py)

- [`RecordingModel`](../tests/test_message_history.py#L39-L53) is the test version of `PeekingModel`: it stores each input in `calls` instead of printing it. `Field(default_factory=list)` gives every instance its own list.
- [`make_history`](../tests/test_message_history.py#L56-L70) builds the 7-message history of turn 1 plus turn 2 halfway through its tool call. It goes through `add_messages` so the messages get ids, as in a real run. [`run_four_turns`](../tests/test_message_history.py#L73-L90) repeats `main`'s run on `InMemorySaver`, with fresh scripts.
- [`test_trimming_does_not_touch_state`](../tests/test_message_history.py#L93-L106): the request is `system human ai tool`, while `history` still has 7 messages. A plain dict works as the state because `model_input` only reads keys.
- [`test_tool_pairs_stay_together`](../tests/test_message_history.py#L109-L128) tries every prefix of the history with every window size from 1 to 8. Each non-empty window starts with a `HumanMessage`, and each `ToolMessage` has its tool call earlier in the same window. [Line 127](../tests/test_message_history.py#L127) is the contrast: the same trim without `start_on` starts with a `ToolMessage`.
- [`test_summary_only_past_threshold_and_old_messages_deleted`](../tests/test_message_history.py#L131-L152) checks the message counts and summaries after each turn, and [line 150](../tests/test_message_history.py#L150) checks that `get_state` agrees with the last result.
- [`test_what_the_models_received`](../tests/test_message_history.py#L155-L169): the model's input sizes `[2, 4, 6, 4, 6, 4, 6]` include the system message, and every input starts with system and then human. The summarizer got 5 and 7 messages, and the second input holds turns 2 and 3 plus the "extend" instruction.
- [`test_remove_message_needs_a_real_id`](../tests/test_message_history.py#L172-L180) calls `add_messages` directly, the same function the graph applies to `summarize`'s update: a real id removes one message, the id `"nope"` raises `ValueError`.
- [`test_long_turn_skips_the_summary`](../tests/test_message_history.py#L183-L211) runs two turns, and turn 2 is one reply with two parallel tool calls, so the thread holds 9 messages (`human ai tool ai human ai tool tool ai`). That is past `SUMMARIZE_AFTER`, so `route_after_model` sends the turn to `summarize`, but the guard returns `{}`. The test checks that all 9 messages and the final answer survive, that there is no `summary` key, and that `summarizer.calls` is empty: the summarizer was never asked.

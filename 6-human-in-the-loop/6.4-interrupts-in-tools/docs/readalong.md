# 6.4 Approving Tool Calls Inside an Agent — code walkthrough

A to-do agent, built like 4.2's hand-made tool loop, holds one conversation of four turns. It may add tasks freely, but its `delete_task` tool calls `interrupt()` itself. So the agent pauses inside the "tools" node, and the human's answer comes back as the tool's result. Run it with `./run.sh 6.4` from the course root.
The concept itself is explained in the [notes](notes.md).

This is a new example ("todo-agent"), so every file is new. The loop itself is 4.2's (see [4.2's read-along](../../../4-agents/4.2-tool-calling-loop/docs/readalong.md)), and pausing, resuming and the restart rule come from 6.1-6.3. This walkthrough only points back to them.

## [todos.py](../src/l6_4_interrupts_in_tools/todos.py)

The data the agent changes and the two tools that change it. All the approval logic is in this file. The graph in `agent.py` knows nothing about it.

### The store ([lines 14-38](../src/l6_4_interrupts_in_tools/todos.py#L14-L38))

- [`TODO_LIST`](../src/l6_4_interrupts_in_tools/todos.py#L15), [`TOOL_RUNS`](../src/l6_4_interrupts_in_tools/todos.py#L22) and [`ADDED_BY_CALL`](../src/l6_4_interrupts_in_tools/todos.py#L25) are module globals, not graph state. LangGraph does not save them in the checkpoint and does not roll them back on resume, just like 6.3's `MANAGER_INBOX`. They play the part of the outside world: whatever a tool does to them stays done, even if LangGraph later runs the tool again.
- `TOOL_RUNS` counts how often each tool function *starts*. It is the evidence that a tool runs again on resume.
- [`reset_todo_list`](../src/l6_4_interrupts_in_tools/todos.py#L29-L34) clears all three globals and puts back the two starting tasks. [Line 37](../src/l6_4_interrupts_in_tools/todos.py#L37) calls it once at import time. The tests call it again before each test, because the globals outlive any single graph.

### [`add_task`](../src/l6_4_interrupts_in_tools/todos.py#L43-L62)

- `@tool` on [line 43](../src/l6_4_interrupts_in_tools/todos.py#L43) turns the function into a langchain_core tool, as in 4.2. The name, the one-line docstring and the type hints become what the model sees.
- The `tool_call_id` parameter on [line 44](../src/l6_4_interrupts_in_tools/todos.py#L44) is annotated with `InjectedToolCallId`. That annotation removes it from the schema the model sees, so the model is only asked for `title`. When ToolNode runs the call, it fills the parameter in with the id of the model's tool call (`"call_1"`, `"call_4"`, ...). Because the value is injected, you cannot call `add_task.invoke({"title": ...})` on its own: it needs a full tool call. That is why the tests drive the tools through the graph.
- [Lines 58-62](../src/l6_4_interrupts_in_tools/todos.py#L58-L62) make the tool idempotent. The first run for a given call id adds the task and remembers its number in `ADDED_BY_CALL`. A second run with the same id adds nothing and returns the same text. The tool has no `interrupt()` of its own, but the check is needed anyway. It only matters in Turn 4, where `add_task` shares a model reply with `delete_task` and runs again on resume (see [`build_agent`](../src/l6_4_interrupts_in_tools/agent.py#L85-L89)). This is 6.3's restart rule ([notes](../../6.3-rules-of-interrupts/docs/notes.md#idempotent-safe-to-repeat)) applied one level down: here the code that repeats is a sibling tool in the same node, not code before `interrupt()` in the same function.
- The tool call id works as the key because LangGraph does not call the model again on resume. The AIMessage with its tool calls is already saved, so the resumed node sees the same ids.

### [`delete_task`](../src/l6_4_interrupts_in_tools/todos.py#L69-L102)

- [Lines 74-75](../src/l6_4_interrupts_in_tools/todos.py#L74-L75) answer an unknown task number at once. There is nothing to approve, so the run does not pause (the first test checks this with task 9).
- [Lines 84-91](../src/l6_4_interrupts_in_tools/todos.py#L84-L91) are the pause. `interrupt()` works inside a tool exactly as it works inside a node (6.1): it raises `GraphInterrupt`, and the payload dict becomes the `Interrupt.value` the caller sees. The interesting part is what ToolNode does with that exception. ToolNode normally catches tool errors, but it re-raises `GraphBubbleUp` (the parent class of `GraphInterrupt`) before its error handling runs. So the pause leaves the tool, leaves ToolNode and stops the whole run. It never turns into an "Error: ..." ToolMessage, and `handle_tool_errors=True` would not change that.
- On resume ToolNode calls `delete_task` again from its first line, as 6.1 showed for nodes. [Line 72](../src/l6_4_interrupts_in_tools/todos.py#L72) therefore counts two runs per approved delete, and line 76 reads the title again. This time `interrupt()` returns the value from `Command(resume=...)`.
- [Line 96](../src/l6_4_interrupts_in_tools/todos.py#L96) accepts only the exact string `"yes"`. Everything else is a rejection: other text, `"Yes"`, or a dict. The test runs all three. Failing closed has a second reason, given in the comment on lines 92-95. If the code after `interrupt()` crashed on an unexpected answer (say by indexing into a string), the saved resume value would be replayed on every later resume, and the thread could not get past it.
- The two `return` lines, [line 99](../src/l6_4_interrupts_in_tools/todos.py#L99) and [line 102](../src/l6_4_interrupts_in_tools/todos.py#L102), are how the human's decision reaches the model. ToolNode wraps whatever string the tool returns into a ToolMessage for this call's id. A rejection is therefore a normal tool result with status `"success"`, not an error. The loop goes back to `call_model` as after any tool call, and the model reads the human's own words.
- [`TOOLS`](../src/l6_4_interrupts_in_tools/todos.py#L108) is the one list given both to `bind_tools` and to `ToolNode`, as in 4.2.

## [agent.py](../src/l6_4_interrupts_in_tools/agent.py)

The agent loop. It mirrors 4.2's `chatbot.py` on purpose, so you can compare the two files line by line. The real differences are the checkpointer and that 6.4 drops 4.2's system prompt.

### The fake model ([lines 24-63](../src/l6_4_interrupts_in_tools/agent.py#L24-L63))

- [`ToolCallingFakeModel`](../src/l6_4_interrupts_in_tools/agent.py#L25-L35) is 4.2's fake: `GenericFakeChatModel` with a `bind_tools` that returns the model itself, because the scripted replies already name the tools.
- [`make_model`](../src/l6_4_interrupts_in_tools/agent.py#L38-L48) wraps the script in an iterator. That matters here: the replies are used up in order across every invoke of the thread, the pause and the resume included. If the model were called once more than planned, the run would fail with `RuntimeError: generator raised StopIteration`. The tests use this as proof that the model is not called again on resume: a script of exactly two replies is enough for a pause plus a resume.
- [`asks_for`](../src/l6_4_interrupts_in_tools/agent.py#L51-L60) builds an AIMessage with one or more tool calls, each with a fixed id. Fixed ids are what make the output stable and let `__main__.py` print them. Several calls in one reply are how a real model asks for parallel tool calls (Turn 4).

### [`build_agent`](../src/l6_4_interrupts_in_tools/agent.py#L67-L98)

- [Lines 76-81](../src/l6_4_interrupts_in_tools/agent.py#L76-L81) are 4.2's `call_model`: send the whole conversation, return only the reply, and let the `MessagesState` reducer append it.
- [Line 89](../src/l6_4_interrupts_in_tools/agent.py#L89) adds the prebuilt `ToolNode` under the name `"tools"`, which is the name `tools_condition` returns on [line 92](../src/l6_4_interrupts_in_tools/agent.py#L92). What matters for this lesson is how ToolNode runs a reply with several tool calls. It runs all of them inside its one task, spread over a thread pool, and returns their ToolMessages together when the node finishes. If one call pauses, the node does not finish, so no ToolMessage from that reply is written to the state, not even for a call that already completed. On resume LangGraph runs the pending "tools" task again, which means every call of that reply runs again. This is why `add_task` needs its idempotency check.
- [Line 93](../src/l6_4_interrupts_in_tools/agent.py#L93) is the back edge from 4.2. After a resume, the finished "tools" node leads back to `call_model` as usual.
- [Line 98](../src/l6_4_interrupts_in_tools/agent.py#L98) compiles with the checkpointer passed in. 4.2 compiled without one. A tool that calls `interrupt()` needs one, because the pause is a saved checkpoint (6.1). At the pause that checkpoint holds the messages up to the AIMessage with the tool call and marks the "tools" task as pending. `call_model` already finished in an earlier step, so its result is saved and it does not run again.

## [\_\_main\_\_.py](../src/l6_4_interrupts_in_tools/__main__.py)

The live run: one thread, four turns.

- [`CONFIG`](../src/l6_4_interrupts_in_tools/__main__.py#L13) uses one `thread_id` for the whole conversation. Unlike 6.1-6.3, where each refund had its own thread, the checkpoint here carries the chat history from turn to turn, and each resume finds its pause through it.
- [`script`](../src/l6_4_interrupts_in_tools/__main__.py#L17-L41) holds eight replies for four turns: one tool request and one final answer per turn. None is needed for a resume. It is a function, so every run gets fresh AIMessage objects (the fake sets their ids). The final answers are fixed text, so the fake says the same thing whatever the tool returned. A real model would read the ToolMessage.
- [`describe`](../src/l6_4_interrupts_in_tools/__main__.py#L48-L58) prints a message as one line: the calls of an AIMessage with their ids, or a ToolMessage with the id it answers. So you can match each result to its request in the output.
- [`step`](../src/l6_4_interrupts_in_tools/__main__.py#L61-L74) runs one invoke, either a new user message or a `Command`, and prints only what that invoke added. [Line 68](../src/l6_4_interrupts_in_tools/__main__.py#L68) counts the saved messages before the invoke. Before the first turn the thread has no checkpoint, so `values` is `{}`, which is why it uses `.get`. [Line 69](../src/l6_4_interrupts_in_tools/__main__.py#L69) uses `version="v2"`, so the state and the pending interrupts come back apart (6.1). [Line 73](../src/l6_4_interrupts_in_tools/__main__.py#L73) prints the question from the tool's payload, never the interrupt id, which changes between runs.
- [Line 82](../src/l6_4_interrupts_in_tools/__main__.py#L82) builds the agent with an `InMemorySaver`.

### Turn 1: adding ([lines 84-90](../src/l6_4_interrupts_in_tools/__main__.py#L84-L90))

`add_task` has no `interrupt()`, so the one invoke on [line 88](../src/l6_4_interrupts_in_tools/__main__.py#L88) runs model, tools, model to the end. Nothing pauses, and the new task gets number 3.

### Turn 2: approving a delete ([lines 93-112](../src/l6_4_interrupts_in_tools/__main__.py#L93-L112))

- [Line 95](../src/l6_4_interrupts_in_tools/__main__.py#L95) stops inside `delete_task`. The output shows the AIMessage asking for `call_2`, then the question.
- [Lines 100-106](../src/l6_4_interrupts_in_tools/__main__.py#L100-L106) look at the saved checkpoint. `next` is `('tools',)` and the only task is `tools`: the pause is in the tool node, not in `call_model`. The last saved message is the AIMessage, and there is no ToolMessage for `call_2` yet. So for now the history breaks 4.2's [pairing rule](../../../4-agents/4.2-tool-calling-loop/docs/notes.md#the-pairing-rule); only the resume completes it.
- [Line 109](../src/l6_4_interrupts_in_tools/__main__.py#L109) resumes with `"yes"`. Only the "tools" node runs again: `delete_task` starts from the top, `interrupt()` returns `"yes"`, and the returned string becomes the ToolMessage for `call_2`. Then the back edge calls the model for its final answer. [Line 110](../src/l6_4_interrupts_in_tools/__main__.py#L110) prints 2 runs of `delete_task`.

### Turn 3: rejecting a delete ([lines 115-122](../src/l6_4_interrupts_in_tools/__main__.py#L115-L122))

The same pause, but [line 120](../src/l6_4_interrupts_in_tools/__main__.py#L120) resumes with free text. The tool keeps the task and returns "Not deleted: ..." with the human's words. Nothing raises, and the loop goes on to the model as after any other tool result.

### Turn 4: adding and deleting in one reply ([lines 125-139](../src/l6_4_interrupts_in_tools/__main__.py#L125-L139))

- [Line 127](../src/l6_4_interrupts_in_tools/__main__.py#L127) remembers the `add_task` count, so the turn can print its own runs.
- The model's reply on [lines 36-39](../src/l6_4_interrupts_in_tools/__main__.py#L36-L39) asks for `add_task` and `delete_task` together, so both run in the same "tools" task. At the pause ([lines 131-132](../src/l6_4_interrupts_in_tools/__main__.py#L131-L132)) `add_task` has run once and task 4 is already on the list, yet no ToolMessage was saved for `call_4`.
- After the resume on [line 137](../src/l6_4_interrupts_in_tools/__main__.py#L137) both calls run again, and both ToolMessages appear, in call order. `add_task` has now run twice, but the list holds "water the plants" only once, thanks to the `ADDED_BY_CALL` check.
- `add_task` comes first in the reply on purpose. With `delete_task` first, whether `add_task` even starts before the pause depends on thread timing. The lesson and the tests avoid that order, so they do not depend on it.

## [test_tool_interrupts.py](../tests/test_tool_interrupts.py)

Each test builds its own agent, script and thread. The autouse fixture [`reset_list`](../tests/test_tool_interrupts.py#L24-L28) resets the module globals before each test.

- [`test_add_never_pauses_and_unknown_delete_needs_no_approval`](../tests/test_tool_interrupts.py#L31-L51): no interrupts, and `next == ()` at the end.
- [`test_delete_pauses_in_tools_node_and_resumes_with_tool_result`](../tests/test_tool_interrupts.py#L54-L87) checks the payload, the saved state while paused (`["human", "ai"]`, pending task `tools`), and then the ToolMessage's content, id, name and status `"success"`. Its script has exactly two replies, so a call to the model on resume would make it fail.
- [`test_any_answer_but_yes_is_a_rejection`](../tests/test_tool_interrupts.py#L90-L107) resumes with three different non-"yes" answers. Each one ends as a normal ToolMessage with the list unchanged.
- [`test_sibling_tool_call_reruns_on_resume_and_stays_idempotent`](../tests/test_tool_interrupts.py#L110-L139) is Turn 4 in isolation: one `add_task` run and no ToolMessage at the pause, two runs and one added task after the resume.
- [`test_main_output`](../tests/test_tool_interrupts.py#L142-L156) runs `main()` and checks the key lines of the output. It imports `main` inside the test, after the fixture has reset the list.

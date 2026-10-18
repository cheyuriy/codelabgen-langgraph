# 4.3 The Prebuilt Agent with create_agent — code walkthrough

The program builds the 4.2 calculator agent again, this time with one call to langchain's `create_agent`, and runs it next to the hand-built graph. First it streams both on the same question and compares the steps. Then it inspects what `create_agent` returned: a normal compiled LangGraph graph. Last, it runs a reply that asks for two tools at once. Run it with `./run.sh 4.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 4.2

The example continues [4.2](../../4.2-tool-calling-loop/docs/readalong.md). [tools.py](../src/l4_3_create_agent/tools.py) and [chatbot.py](../src/l4_3_create_agent/chatbot.py) are copied unchanged. The only edit is the package name in the import on [line 21 of chatbot.py](../src/l4_3_create_agent/chatbot.py#L21). 4.2's read-along explains both files. The fake model, `SYSTEM_PROMPT`, `tool_call`, `unanswered_tool_calls` and the hand-built `build_graph` are reused here as they are.

- [pyproject.toml](../pyproject.toml#L10) adds `langchain==1.4.6`. `create_agent` lives in the `langchain` package, not in `langgraph`. Its own requirements are already covered by 4.2's pins, so this line adds only the `langchain` package itself.
- New file [agent.py](../src/l4_3_create_agent/agent.py) with [`build_agent`](../src/l4_3_create_agent/agent.py#L25-L57) and [`edges`](../src/l4_3_create_agent/agent.py#L64-L74).
- [\_\_main\_\_.py](../src/l4_3_create_agent/__main__.py) is rewritten. [`describe`](../src/l4_3_create_agent/__main__.py#L14-L24) is the same as in 4.2. The new [`script`](../src/l4_3_create_agent/__main__.py#L27-L38) helper returns the model's replies, and `main` has three new sections.
- 4.2's tests are not carried over. The new tests are in [test_create_agent.py](../tests/test_create_agent.py).

## [agent.py](../src/l4_3_create_agent/agent.py)

The same agent as `chatbot.build_graph`, but the graph is built by the library.

- [Line 7](../src/l4_3_create_agent/agent.py#L7) imports `create_agent` from `langchain.agents`. This is the current import. [Lines 14–21](../src/l4_3_create_agent/agent.py#L14-L21) show the old `create_react_agent` from `langgraph.prebuilt` only as a comment. Importing and calling it would still work, but it gives a deprecation warning. Two things changed when it moved: the keyword `prompt=` is now `system_prompt=`, and the model node is named `"model"` instead of `"agent"`. If you pass `prompt=` to `create_agent`, you get a `TypeError` right away, because the parameter doesn't exist.

### build_agent

- [`build_agent`](../src/l4_3_create_agent/agent.py#L25-L57) is one line of real code: the call on [line 57](../src/l4_3_create_agent/agent.py#L57). It gets the same `TOOLS` list and the same `SYSTEM_PROMPT` as `build_graph`, so the two graphs differ only in who built them. `system_prompt` is keyword-only. The model and the tools are passed by position.
- What `create_agent` builds, compared with `build_graph` in 4.2:
  - A `"model"` node in place of `call_model`, and a `"tools"` node that is the same `ToolNode` from `langgraph.prebuilt`. The tools node is added only because a tool list was given. With an empty list, the graph would have no tools node and no loop.
  - The `"model"` node binds the tools on every model call ([lines 37–41](../src/l4_3_create_agent/agent.py#L37-L41)), with `tool_choice=None`. 4.2 bound them once, when the graph was built. The fake model's `bind_tools` returns `self`, so being called four times does no harm. A real chat model would build a new bound runnable on each call.
  - The system prompt is put in front of the messages on each call, and it is never written to the state. So the history in the result has no `SystemMessage`, the same as in 4.1 and 4.2. Section (c) of `main` shows this.
  - The routing after `"model"` is not `tools_condition` ([lines 42–46](../src/l4_3_create_agent/agent.py#L42-L46)). `create_agent` adds its own conditional edge. It sends every pending tool call to `"tools"` as a separate `Send`, so each call runs as its own task. All of these tasks run in the same super-step. In 4.2, one `tools` step ran all calls of a reply together. The edge back from `"tools"` to `"model"` is conditional too, because a tool marked `return_direct=True` can end the run without asking the model again. Our tools don't use that, so the run always goes back to the model.
  - The compiled graph has a default `recursion_limit` of 9999 ([lines 47–48](../src/l4_3_create_agent/agent.py#L47-L48)). A plain compiled graph uses LangGraph's general default. The limit you pass to `invoke` or `stream` replaces it, and `main` always passes one.
- The docstring names the state schema, `AgentState`. It holds `messages`, which works just like `MessagesState` in 4.2, plus `structured_response`, which stays empty unless you pass `response_format`. The private `jump_to` key is for middleware and doesn't appear in the output.
- [Lines 50–56](../src/l4_3_create_agent/agent.py#L50-L56) list the other keyword arguments. They are how you change the prebuilt loop without writing the graph yourself. The lesson uses none of them. `checkpointer=` comes back in module 5.

### edges

- [`edges`](../src/l4_3_create_agent/agent.py#L64-L74) works on any compiled graph, so it can compare the two graphs line by line. `graph.get_graph()` on [line 73](../src/l4_3_create_agent/agent.py#L73) returns the drawable graph, the same one behind the Mermaid diagrams in modules 1–3. Each edge has `source`, `target` and a `conditional` flag. [Line 72](../src/l4_3_create_agent/agent.py#L72) turns the flag into the Mermaid arrows: `-.->` for conditional, `-->` for fixed.
- The list is sorted, so the result doesn't depend on the order in which the graph was built, and it can be compared directly in the tests.

## [\_\_main\_\_.py](../src/l4_3_create_agent/__main__.py)

The entry point. [`main`](../src/l4_3_create_agent/__main__.py#L41-L119) runs three sections.

- [`describe`](../src/l4_3_create_agent/__main__.py#L14-L24) is copied from 4.2. It never prints message ids, because they are random and would change the output on every run.
- [`script`](../src/l4_3_create_agent/__main__.py#L27-L38) is a function, not a constant. The fake model writes an id onto each `AIMessage` it returns. If the agent and the hand-built graph shared one list, both would use the same message objects, and the second run would see ids left by the first. A new list for each model avoids that.

### create_agent runs the same loop

- [Line 45](../src/l4_3_create_agent/__main__.py#L45) builds the agent with the same fake model as 4.2. No adapter is needed: `create_agent` accepts any chat model that has `bind_tools`.
- [Lines 50–54](../src/l4_3_create_agent/__main__.py#L50-L54) stream the agent the same way 4.2 streamed its own graph. [Line 52](../src/l4_3_create_agent/__main__.py#L52) sets `recursion_limit` to 10. The run takes 7 steps, four model calls and three tool steps, so it needs a limit of at least 8. Without this, the agent's 9999 would apply.
- In the loop on [lines 57–60](../src/l4_3_create_agent/__main__.py#L57-L60), `delta["messages"]` on line 59 holds only what that node added. `"model"` returns one `AIMessage`, and `"tools"` returns the `ToolMessage` of its single call.
- [Lines 63–69](../src/l4_3_create_agent/__main__.py#L63-L69) stream the hand-built graph with its own new script. `hand_nodes.extend(update)` on line 69 works because iterating over a dict gives its keys, here the node name of each update.
- [Lines 71–72](../src/l4_3_create_agent/__main__.py#L71-L72) print both node orders. They have the same length and the same pattern. Only the model node's name is different. Each step also added the same messages, which `test_same_result_as_hand_built_graph` checks.

### Underneath: a compiled LangGraph graph

- [Line 79](../src/l4_3_create_agent/__main__.py#L79) builds a hand-built graph only to inspect it. Building a graph doesn't call the model, so an empty script is enough.
- [Line 83](../src/l4_3_create_agent/__main__.py#L83) prints `CompiledStateGraph`, the same class that `builder.compile()` returns. This is the main point of the lesson: everything you learned for your own graphs (`stream`, stream modes, `get_graph`, `recursion_limit`, and later checkpointers and interrupts) works on the agent too.
- [Lines 84–85](../src/l4_3_create_agent/__main__.py#L84-L85) print the edges of both graphs. The shape is the same: start, model, a conditional edge to `tools` or `__end__`, and an edge back. There is one difference. The edge `tools -.-> model` is conditional in the agent (the `return_direct` check) but fixed in 4.2 (`tools --> call_model`). The `Send` routing appears in the drawing as a plain conditional edge `model -.-> tools`. The drawing shows where a step can go, not how many tasks start.
- [Lines 86–91](../src/l4_3_create_agent/__main__.py#L86-L91) compare the output schemas. `get_output_jsonschema()` describes the keys a run returns. The agent has `structured_response` in addition to `messages`, which comes from `AgentState`.
- [Line 94](../src/l4_3_create_agent/__main__.py#L94) reads `agent.config`. This is the config that `create_agent` attached with `.with_config`, and it holds the default `recursion_limit` of 9999.

### Two tool calls in one reply

- [Lines 100–106](../src/l4_3_create_agent/__main__.py#L100-L106) build a reply with two tool calls directly, as in 4.2, because `tool_call` makes only single calls. [Line 107](../src/l4_3_create_agent/__main__.py#L107) gives a new agent its own script, and `agent` is reused as a variable name.
- [Lines 108–111](../src/l4_3_create_agent/__main__.py#L108-L111) use `invoke`, not `stream`. The routing sends `call_a` and `call_b` as two `Send` tasks to `"tools"`, and both run in one super-step. So the run still takes 3 steps (model, tools, model), and `test_two_tool_calls_in_one_reply` shows that a limit of 3 fails and 4 works. In a stream, the two tasks give two separate `tools` updates, and their order is not fixed. In the final state, the `ToolMessage`s are always in call order. That is why the section prints the result, not the stream.
- [Line 118](../src/l4_3_create_agent/__main__.py#L118) runs 4.2's pairing check on the agent's history: every call has its answer, so it prints `[]`.
- [Line 119](../src/l4_3_create_agent/__main__.py#L119) counts `SystemMessage`s in the state and prints 0. The system prompt was sent to the model on every call but never stored.
- [Line 122](../src/l4_3_create_agent/__main__.py#L122) is only a pointer: module 5 adds memory to this agent.

## [test_create_agent.py](../tests/test_create_agent.py)

The tests check the live run and what `create_agent` does inside.

- [`script`](../tests/test_create_agent.py#L24-L31) and [`parallel_script`](../tests/test_create_agent.py#L34-L45) build new message objects for each test, for the same reason as `script` in `main`. [`stream_nodes`](../tests/test_create_agent.py#L53-L58) collects node names the same way as line 69 of `__main__.py`.
- [`test_same_result_as_hand_built_graph`](../tests/test_create_agent.py#L61-L76) runs both graphs and compares message types and contents (line 70). The agent and the hand-built loop produce the same history.
- [`test_loop_shape_and_recursion_limit`](../tests/test_create_agent.py#L79-L89): 7 fails and 8 works, the same as in 4.2. Line 89 checks the default of 9999.
- [`RecordingModel`](../tests/test_create_agent.py#L98-L115) subclasses the lesson's fake to see what `create_agent` does to the model. The records go into the module-level lists on [lines 94–95](../tests/test_create_agent.py#L94-L95), because a chat model is a pydantic object and doesn't accept new attributes. [`test_what_the_model_receives`](../tests/test_create_agent.py#L118-L134) confirms the facts from `build_agent`'s comments: `bind_tools` is called four times, once per model call, with `{"tool_choice": None}` (line 128). Every model input starts with the system prompt (lines 132–133), and the final state has no `SystemMessage` (line 134).
- [`test_it_is_a_compiled_graph`](../tests/test_create_agent.py#L137-L153) checks the class, the edges of both graphs and the output keys printed by section (b).
- [`test_two_tool_calls_in_one_reply`](../tests/test_create_agent.py#L156-L177) checks call order in the state (line 164). For the stream it compares a sorted list (line 170), because the order of the two `tools` updates varies. Lines 172–177 show that both calls fit into one super-step.
- [`test_tool_errors_behave_as_in_4_2`](../tests/test_create_agent.py#L180-L192): `create_agent`'s `ToolNode` has the default error handling. `ZeroDivisionError` from `divide` ends the run (line 184), and the unknown tool `subtract` becomes an error `ToolMessage` that the model can answer (lines 190–192). Unlike in 4.2, you can't pass `handle_tool_errors` to this `ToolNode`. To change this behaviour you use middleware.

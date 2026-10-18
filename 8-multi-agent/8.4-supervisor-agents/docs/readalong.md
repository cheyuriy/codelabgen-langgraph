# 8.4 A Supervisor with Specialist Agents as Tools — code walkthrough

A support supervisor answers customer questions. It does not look anything up itself: it calls a billing agent and a shipping agent, and each of them is wrapped as an ordinary tool. All three are `create_agent` agents with scripted fake models, so the run is offline and prints the same lines every time. Run it with `./run.sh 8.4` from the course root.
The concept itself is explained in the [notes](notes.md).

This is a new example. It does not import anything from 8.1-8.3 or 4.3, but the agents are built the same way as in [lesson 4.3](../../../4-agents/4.3-create-agent/docs/readalong.md).

## [fake_model.py](../src/l8_4_supervisor_agents/fake_model.py)

The scripted model that all three agents use. A real chat model would decide which tool to call. Here the script makes that decision, and everything around it (tool calls, `ToolNode`, nested runs) is real LangGraph.

- [`ToolCallingFakeModel`](../src/l8_4_supervisor_agents/fake_model.py#L15-L31) only adds [`bind_tools`](../src/l8_4_supervisor_agents/fake_model.py#L24-L31). `create_agent` binds the tools to the model before each model call, so that a real model knows their names and argument schemas. The fake does not need them, because the scripted replies already name the tools. Returning `self` is enough.
- [`make_model`](../src/l8_4_supervisor_agents/fake_model.py#L34-L40) passes the replies as an iterator (`iter(replies)` on line 40). Each model call takes the next reply. When the iterator is empty, the next call fails. This is why every section in `__main__.py` builds new models and new agents: a model can only go through its script once.
- `GenericFakeChatModel` writes an `id` onto the `AIMessage` objects it returns. These are the same objects as in the script list, so two models must never share one list. The functions in `scripts.py` therefore build a new list on every call.
- [`tool_call`](../src/l8_4_supervisor_agents/fake_model.py#L43-L45) builds a reply with exactly one tool call. The `**args` become the call's arguments, so `tool_call("track_order", "ship_1", order_id="ORD-1042")` asks for `track_order(order_id="ORD-1042")`. The `call_id` is what the `ToolMessage` with the result will point back to.

## [specialists.py](../src/l8_4_supervisor_agents/specialists.py)

The two specialists. Each one is a complete agent with one tool and its own system prompt. Nothing in this file knows that a supervisor exists.

- [`INVOICES` and `ORDERS`](../src/l8_4_supervisor_agents/specialists.py#L13-L14) are the "databases": invoice INV-2077 is the double charge from 8.3, and ORD-1042 is a new order.
- [`lookup_invoice`](../src/l8_4_supervisor_agents/specialists.py#L17-L20) and [`track_order`](../src/l8_4_supervisor_agents/specialists.py#L23-L26) are plain `@tool` functions, as in 4.3. The decorator turns the function name into the tool name, the docstring into the description and the parameter into the argument schema. An unknown id returns a text, not an exception, so the agent can read the answer and go on.
- [`build_billing_agent`](../src/l8_4_supervisor_agents/specialists.py#L42-L44) and [`build_shipping_agent`](../src/l8_4_supervisor_agents/specialists.py#L47-L49) each return a compiled graph with the nodes `model` and `tools`. The comment on [lines 35-39](../src/l8_4_supervisor_agents/specialists.py#L35-L39) explains `name=`. It matters later: in the trace, the specialist's AI messages are signed `shipping` or `billing`, and section 2 uses this name to tell the two runs apart.

## [supervisor.py](../src/l8_4_supervisor_agents/supervisor.py)

The supervisor. Its tools are the two specialist agents.

- [`as_tool`](../src/l8_4_supervisor_agents/supervisor.py#L11-L36) is the central idea of the lesson: it turns a compiled agent into a tool. `@tool(name, description=description)` on line 16 creates a tool with the name and description given as arguments, not taken from the function. So one `ask` function can become `ask_billing` and `ask_shipping`. The docstring of `ask` is not used as the description. The tool's only argument is `request`, a string the supervisor's model writes.
- [Line 30](../src/l8_4_supervisor_agents/supervisor.py#L30) is where one agent runs another. The specialist gets a new input with only one `HumanMessage`, the request. It does not get the supervisor's `messages`, so it never sees the customer's question or the supervisor's history. The test `test_specialist_sees_only_the_request` checks this.
- `agent.invoke` gets no config, but the specialist run is still part of the supervisor's run. While a node runs, LangGraph keeps the current config in a Python context variable, and a graph invoked inside the node reads it from there. That is why the specialist's steps show up in the supervisor's `stream(subgraphs=True)` in section 1.
- [Line 34](../src/l8_4_supervisor_agents/supervisor.py#L34) returns only the last message's text. `ask` returns a plain string. The supervisor's `ToolNode` wraps it in a `ToolMessage` with the `tool_call_id` of the call and the tool name. The specialist's own tool call and its `ToolMessage` stay in the specialist's result, which is thrown away here. What this line returns is all the supervisor learns from the specialist. The first experiment changes it.
- [`build_supervisor`](../src/l8_4_supervisor_agents/supervisor.py#L48-L74) is a normal `create_agent` call with two tools. `create_agent` does not know that these tools run agents. When one model reply has two tool calls, `create_agent` sends each call to its own `tools` task, and both tasks run in the same super-step. After the tools, the graph always goes back to the supervisor's `model` node, so the supervisor decides what comes next and writes the answer to the customer.

## [scripts.py](../src/l8_4_supervisor_agents/scripts.py)

The replies of the three fake models and the two customer questions. Each script is what a real model would probably answer, written down in advance.

- [`billing_script`](../src/l8_4_supervisor_agents/scripts.py#L18-L23) and [`shipping_script`](../src/l8_4_supervisor_agents/scripts.py#L26-L31) have two replies each: one tool call, then the answer. So each specialist run makes two model calls.
- [`supervisor_one_script`](../src/l8_4_supervisor_agents/scripts.py#L34-L41) asks only the shipping specialist. The `request` on line 38 is the supervisor's own wording, not the customer's question. That is the text the specialist receives.
- [`supervisor_two_script`](../src/l8_4_supervisor_agents/scripts.py#L44-L66) builds the first reply by hand, because `tool_call` only makes one call per reply. [Lines 49-60](../src/l8_4_supervisor_agents/scripts.py#L49-L60) put two calls, `call_1` to billing and `call_2` to shipping, into one `AIMessage`. This is what lets the two specialists run in parallel in section 2.

## [show.py](../src/l8_4_supervisor_agents/show.py)

Helpers that turn messages and namespaces into short, stable lines. They never print message ids, because the ids change from run to run.

- [`label`](../src/l8_4_supervisor_agents/show.py#L9-L11) prints the message's `name` when there is one. The AI messages carry the agent's name from `create_agent(name=...)`. The human message has no name, so it is printed as `human`.
- [`describe`](../src/l8_4_supervisor_agents/show.py#L14-L24) has three cases: an AI message with tool calls, a `ToolMessage` and anything else. For a `ToolMessage`, `name` is the tool's name (`ask_shipping`, `track_order`), set by `ToolNode`, not an agent's name.
- [`node_path`](../src/l8_4_supervisor_agents/show.py#L27-L32) is the same as in 8.3. A specialist run started inside the supervisor's `tools` node has the namespace `("tools:<task id>",)`, which is printed as `tools`.

## [\_\_main\_\_.py](../src/l8_4_supervisor_agents/__main__.py)

The run, in three sections. [`CONFIG`](../src/l8_4_supervisor_agents/__main__.py#L22) sets `recursion_limit` to 10. The limit counts the supervisor's super-steps only. The steps of the nested specialist runs do not count against it: the tools call `agent.invoke` without a config, and `create_agent` compiles every agent with a `recursion_limit` of 9 999, so this limit would not stop a looping specialist.

**Section 1, one question through two levels** ([lines 27-49](../src/l8_4_supervisor_agents/__main__.py#L27-L49)):

- The billing agent on [line 32](../src/l8_4_supervisor_agents/__main__.py#L32) gets an empty script. It is never called here, and if it were, it would fail at once.
- [Lines 40-45](../src/l8_4_supervisor_agents/__main__.py#L40-L45) stream with `stream_mode="updates"` and `subgraphs=True`. Each item is a pair `(namespace, update)`. Without `subgraphs=True` you would only get the supervisor's own updates, and the specialist run would stay hidden inside one `tools` step (the last experiment).
- The output shows the order of a request through both levels: the supervisor's `model` asks for `ask_shipping`, then three lines from inside `tools` (the shipping agent's `model`, `tools`, `model`), then the supervisor's `tools` update with the `ToolMessage`, and the supervisor's final answer. The supervisor's `tools` update comes after the inner lines because the node only finishes when the specialist has answered.
- The specialist's input `HumanMessage` is not printed. It is the input of the inner run, not an update of a node.

**Section 2, two specialists in one step** ([lines 52-92](../src/l8_4_supervisor_agents/__main__.py#L52-L92)):

- The two specialist runs run at the same time, so their nested updates can come in a different order from run to run. This section does not print them one by one. It prints summaries that are always the same.
- [Line 71](../src/l8_4_supervisor_agents/__main__.py#L71) asks for two stream modes at once. With a list of modes and `subgraphs=True`, each item is a triple `(namespace, mode, data)`.
- The `values` items with an empty namespace are full snapshots of the supervisor's state. [Line 76](../src/l8_4_supervisor_agents/__main__.py#L76) keeps the latest one, so after the loop `final_state` is the final state.
- [Line 80](../src/l8_4_supervisor_agents/__main__.py#L80) collects the supervisor's own steps. The result is `model -> tools -> tools -> model`: two `tools` updates, one for each `Send` task, both in the same super-step.
- [Lines 82-85](../src/l8_4_supervisor_agents/__main__.py#L82-L85) count the nested messages for each namespace. Each specialist run has its own namespace, because each `tools` task has its own task id. The agent's name comes from the first named `AIMessage` in that namespace. The `ToolMessage` cannot be used for this, because its name is the tool name. Each run has 3 messages: the tool call, the tool result and the answer.
- [Lines 90-91](../src/l8_4_supervisor_agents/__main__.py#L90-L91) print the supervisor's history. It has five messages: the question, one AI message with both calls, two `ToolMessage`s in call order and the answer. None of the specialists' `lookup_invoice` or `track_order` messages are there.

**Section 3, a specialist on its own** ([lines 95-104](../src/l8_4_supervisor_agents/__main__.py#L95-L104)): the billing agent is invoked directly, like any 4.3 agent. It works without a supervisor because it does not depend on one. Here you can see the whole billing run that section 2 kept out of the supervisor's history.

## [test_supervisor.py](../tests/test_supervisor.py)

The tests check the facts from the run and from the experiments.

- [`RecordingModel`](../tests/test_supervisor.py#L29-L35) overrides `_generate`, the method that a chat model runs on every call. It writes down what the model received before it returns the scripted reply.
- [`test_agent_becomes_a_tool`](../tests/test_supervisor.py#L63-L71) calls the wrapped agent directly, without a supervisor: one `request` argument in, a plain string out.
- [`test_two_part_question_keeps_only_answers`](../tests/test_supervisor.py#L74-L90) checks the section 2 history and that no inner tool call reached it.
- [`test_specialist_sees_only_the_request`](../tests/test_supervisor.py#L93-L108) is the context isolation test. The billing model's first call receives only its system prompt and the supervisor's request ([lines 101-104](../tests/test_supervisor.py#L101-L104)), and no call contains the order number or the customer's text.
- [`test_nested_trace`](../tests/test_supervisor.py#L111-L141) checks the order of section 1 and that every nested namespace starts with `tools:`.
- [`test_parallel_specialists_share_a_step`](../tests/test_supervisor.py#L144-L159) measures the parallel calls with `recursion_limit`. Both calls in one reply need three supervisor super-steps (limit 3 fails, 4 works). With [`split_script`](../tests/test_supervisor.py#L54-L60), one call per reply, they need five (limit 5 fails, 6 works). Each extra reply costs one more model call and two more super-steps.
- [`test_unknown_specialist_gives_error_message`](../tests/test_supervisor.py#L162-L182) calls a tool that does not exist. `ToolNode` does not raise. It returns a `ToolMessage` with `status="error"`, the supervisor's model runs again and gives its scripted answer.

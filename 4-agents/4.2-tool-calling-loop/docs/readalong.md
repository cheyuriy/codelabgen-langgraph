# 4.2 A Tool-Calling Agent Loop by Hand — code walkthrough

The program turns the 4.1 chatbot into a calculator agent. The model asks for tools, a `ToolNode` runs them, and the results go back to the model until it answers without a tool call. First it streams one run step by step. Then it runs a reply that asks for two tools at once and checks that every tool call got an answer. Run it with `./run.sh 4.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 4.1

The example continues [4.1](../../4.1-messages-state/docs/readalong.md). `SYSTEM_PROMPT`, the closure style of `build_graph` and the body of `call_model` are the same, and 4.1's read-along explains them.

- [pyproject.toml](../pyproject.toml#L8) adds `langgraph-prebuilt==1.1.1`. `ToolNode` and `tools_condition` live in that package, and this lesson imports it directly, so it declares it.
- New file [tools.py](../src/l4_2_tool_calling_loop/tools.py) with the three tools and the `TOOLS` list.
- [`ToolCallingFakeModel`](../src/l4_2_tool_calling_loop/chatbot.py#L30-L41) replaces the plain `GenericFakeChatModel`, and [`make_model`](../src/l4_2_tool_calling_loop/chatbot.py#L44-L60) now accepts any iterable of `AIMessage` or `str`.
- New helper [`tool_call`](../src/l4_2_tool_calling_loop/chatbot.py#L63-L70) builds a reply that asks for one tool.
- In [`build_graph`](../src/l4_2_tool_calling_loop/chatbot.py#L77-L113), the model is bound to the tools on [line 87](../src/l4_2_tool_calling_loop/chatbot.py#L87). `call_model` calls the bound model on [line 93](../src/l4_2_tool_calling_loop/chatbot.py#L93). There is a new `"tools"` node, and a conditional edge replaces the `call_model -> END` edge. A new edge leads back from `tools` to `call_model`.
- New function [`unanswered_tool_calls`](../src/l4_2_tool_calling_loop/chatbot.py#L120-L137) checks the pairing rule.
- [\_\_main\_\_.py](../src/l4_2_tool_calling_loop/__main__.py) has two new sections. 4.1's two-turn chat and `add_messages` demo are gone.
- The tests are new: [test_tool_loop.py](../tests/test_tool_loop.py).

## [tools.py](../src/l4_2_tool_calling_loop/tools.py)

The tools the agent can call. They are ordinary Python functions, so they are the easiest part to read first.

- [`add`](../src/l4_2_tool_calling_loop/tools.py#L11-L19), [`multiply`](../src/l4_2_tool_calling_loop/tools.py#L22-L30) and [`divide`](../src/l4_2_tool_calling_loop/tools.py#L33-L41) are each wrapped by `@tool`. After decoration, `add` is no longer a function but a `StructuredTool`. You call it with `add.invoke({"a": 3, "b": 4})`, not `add(3, 4)`. This is why the test on [line 93](../tests/test_tool_loop.py#L93) uses `invoke`.
  - The docstring and the type hints are not just for people. With the default `@tool`, the whole docstring (the `Args:` section included) becomes the tool's description, and the type hints become the argument schema (`int` here). Only `@tool(parse_docstring=True)` would split the `Args:` lines into per-argument descriptions. A real model receives exactly this schema from `bind_tools` and chooses tools by reading it.
  - The hints are also checked at run time. When `ToolNode` gets arguments that don't fit the schema (for example `"three"` for `a`), it returns an error `ToolMessage` and does not call the function.
  - `divide` on [line 41](../src/l4_2_tool_calling_loop/tools.py#L41) has no zero check on purpose. Dividing by zero is one of the experiments: `ToolNode` lets that exception through (see below).
- [`TOOLS`](../src/l4_2_tool_calling_loop/tools.py#L45) is the one list that both the model and `ToolNode` get. If the two lists differed, the model could ask for a tool that the node can't run. The order is kept: `[t.name for t in TOOLS]` is `['add', 'multiply', 'divide']`.

## [chatbot.py](../src/l4_2_tool_calling_loop/chatbot.py)

The model, the graph and the pairing check.

- [Line 19](../src/l4_2_tool_calling_loop/chatbot.py#L19) imports `ToolNode` and `tools_condition` from `langgraph.prebuilt`. Both are ordinary building blocks: a node class and a routing function. You could write them yourself, and the code below would use them in the same places.
- [Line 13](../src/l4_2_tool_calling_loop/chatbot.py#L13) no longer imports `END`. No edge in this graph points to `END` directly: `tools_condition` routes there.

### The fake model

- [`ToolCallingFakeModel`](../src/l4_2_tool_calling_loop/chatbot.py#L30-L41) adds a single method. `bind_tools` on a real chat model returns a new runnable that sends the tool schemas with every request. The fake's replies are already scripted, so [line 41](../src/l4_2_tool_calling_loop/chatbot.py#L41) returns `self`. Without this subclass, `build_graph` would fail on line 87, because `GenericFakeChatModel.bind_tools` raises `NotImplementedError`.
- [`make_model`](../src/l4_2_tool_calling_loop/chatbot.py#L44-L60) still wraps the replies in `iter(...)` on line 60. Since the parameter is now `Iterable`, a generator works too: [`endless`](../tests/test_tool_loop.py#L145-L148) in the tests is a model that never stops asking for tools.
  - The second docstring paragraph is the trap to remember. The fake writes an id onto the `AIMessage` object it returns. `add_messages` merges by id, so if one object appeared twice in a script, the second reply would replace the first in the history. That is why `main` and the tests build each script fresh, for example [`loop_script`](../tests/test_tool_loop.py#L21-L28).
- [`tool_call`](../src/l4_2_tool_calling_loop/chatbot.py#L63-L70) builds what a real model sends when it wants a tool: empty `content` and one entry in `tool_calls`. The `id` matters most. `ToolNode` copies it into the answer's `tool_call_id`, and that is how the result is matched to the request. Real providers generate these ids. Here the script sets readable ones like `call_1`, so the output can show them.

### The graph

- [Line 87](../src/l4_2_tool_calling_loop/chatbot.py#L87) binds the tools once, when the graph is built, not inside the node. The node only uses `model_with_tools` from the enclosing function, the same closure pattern as in 4.1.
- [`call_model`](../src/l4_2_tool_calling_loop/chatbot.py#L90-L96) is unchanged apart from line 93. It doesn't know about tools at all: it returns whatever the model replied, an answer or a request for tools.
- [Line 106](../src/l4_2_tool_calling_loop/chatbot.py#L106) adds `ToolNode(TOOLS)` as a node. `ToolNode` reads the last `AIMessage` from `messages` and runs each of its tool calls. It runs them concurrently in a thread pool but returns the `ToolMessage`s in call order, and each one gets the tool's name, its result as a string (`'7'`, not `7`) and the `tool_call_id`. It returns `{"messages": [...]}`, so `add_messages` appends the results like any node update.
  - With its default error handling, `ToolNode` turns only two kinds of mistakes into an error `ToolMessage`: an unknown tool name and arguments that don't fit the schema. An exception raised inside the tool, such as `ZeroDivisionError`, ends the whole run. [`test_tool_errors_default_handling`](../tests/test_tool_loop.py#L124-L142) checks both cases.
  - The node name `"tools"` is required. `tools_condition` returns that string, and LangGraph looks it up as a node name.
- [Line 110](../src/l4_2_tool_calling_loop/chatbot.py#L110) is the decision point. After every `call_model` step, `tools_condition` looks at the last message. If it is an `AIMessage` with `tool_calls`, it returns `"tools"`, otherwise `"__end__"`, which is the value of `END`. The model decides when the loop ends, by replying without a tool call.
- [Line 112](../src/l4_2_tool_calling_loop/chatbot.py#L112) is the edge that makes a loop. After the tools run, the model is asked again and sees the whole history, including the new `ToolMessage`s. Without this edge, `tools` would have no outgoing edge and the run would stop right after the first tool result.
- [Line 113](../src/l4_2_tool_calling_loop/chatbot.py#L113) compiles without a checkpointer, as in 4.1.

### The pairing check

- [`unanswered_tool_calls`](../src/l4_2_tool_calling_loop/chatbot.py#L120-L137) works in two passes. [Line 130](../src/l4_2_tool_calling_loop/chatbot.py#L130) collects the ids that some `ToolMessage` answers. Lines 131–137 then go through every `AIMessage` and keep the call ids that are not in that set, in history order.
  - It looks only at ids, not at position. If the history were in the wrong order, the check would not notice.
  - A real provider rejects the next request when the check would return anything. The fake model accepts any history, so the lesson needs this function to show the rule.

## [\_\_main\_\_.py](../src/l4_2_tool_calling_loop/__main__.py)

The entry point. [`main`](../src/l4_2_tool_calling_loop/__main__.py#L26-L87) runs the two sections.

- [`describe`](../src/l4_2_tool_calling_loop/__main__.py#L13-L23) prints a message in one line. The order of its checks matters: an `AIMessage` with tool calls is printed as a request (line 15), a `ToolMessage` with its `tool_call_id` and tool name (line 22), and everything else by class name and content. It never prints `m.id`, because the ids are random and would change the output on every run.

### The agent loop, step by step

- [Lines 31–36](../src/l4_2_tool_calling_loop/__main__.py#L31-L36) script the model: three replies that each ask for one tool, then a plain answer. The model asks for one tool at a time, because each step needs the result of the step before. The fake doesn't read the results, but the script follows the order a real model would.
- [Line 47](../src/l4_2_tool_calling_loop/__main__.py#L47) sets `recursion_limit` to 10. The run takes 7 steps (four `call_model`, three `tools`), and 7 steps need a limit of at least 8. If the model kept asking for tools, the default limit of 10007 would let it loop for a very long time. [`test_loop_shape_and_recursion_limit`](../tests/test_tool_loop.py#L59-L88) shows that 7 fails and 8 works.
- [Line 48](../src/l4_2_tool_calling_loop/__main__.py#L48) uses `stream_mode="updates"`. Each item is `{node_name: what_the_node_returned}` for one step, so the loop on lines 51–54 sees the nodes in turn and only the messages each one added, not the full history. The output alternates `call_model` and `tools`, which is the loop made visible.
- The text on [line 56](../src/l4_2_tool_calling_loop/__main__.py#L56) describes what happened after the last step: `tools_condition` saw a reply without tool calls and routed to `END`. `END` is not a node, so it doesn't appear in the stream.

### Two tool calls in one reply

- [Lines 63–69](../src/l4_2_tool_calling_loop/__main__.py#L63-L69) build the `AIMessage` directly, because `tool_call` makes only single calls. This is how a real model asks for independent calculations at once.
- [Line 71](../src/l4_2_tool_calling_loop/__main__.py#L71) uses `invoke` and then prints the final history. The single `tools` step returned two `ToolMessage`s, for `call_a` and `call_b` in that order. That takes 3 steps in total: `call_model`, `tools`, `call_model`.
- [Line 80](../src/l4_2_tool_calling_loop/__main__.py#L80) prints `[]`, because every call has its answer.
- [Lines 82–84](../src/l4_2_tool_calling_loop/__main__.py#L82-L84) build a broken copy of the history without the answer to `call_b`. They make a new list and don't change `messages`. Line 87 then prints `['call_b']`: this is the history a provider would reject.

## [test_tool_loop.py](../tests/test_tool_loop.py)

The tests check the live run and the cases that `main` does not show.

- [`loop_script`](../tests/test_tool_loop.py#L21-L28) and [`parallel_script`](../tests/test_tool_loop.py#L31-L42) are functions, not constants, so each test gets new message objects (the fake writes ids onto them).
- [`test_full_loop`](../tests/test_tool_loop.py#L45-L56) checks the whole history, and line 52 checks that tool results are stored as strings.
- [`test_tools_and_router`](../tests/test_tool_loop.py#L91-L97) calls the tools and `tools_condition` without a graph. `tools_condition` is a plain function of the state, so it can be tested directly. `ToolNode` can't: outside a graph it fails because it needs the graph's config, so it is tested only through `build_graph`.
- [`test_pairing`](../tests/test_tool_loop.py#L100-L121) checks on line 113 that the two answers come right after the request, in call order.
- [`test_tool_errors_default_handling`](../tests/test_tool_loop.py#L124-L142): `divide(a=1, b=0)` raises out of `invoke` (line 127), while the unknown tool `subtract` becomes a `ToolMessage` with status `error` (line 140). The model gets that message and can react to it, so the run ends normally with the scripted reply.
- [`test_endless_loop_hits_recursion_limit`](../tests/test_tool_loop.py#L151-L166) feeds the model from the [`endless`](../tests/test_tool_loop.py#L145-L148) generator. With `recursion_limit=6`, exactly six steps run and then `GraphRecursionError` is raised (line 166). In an agent loop, the recursion limit is the guard against a model that never stops calling tools.

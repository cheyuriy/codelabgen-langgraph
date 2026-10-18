# 4.1 Messages in State and an Offline Chat Model — code walkthrough

The program runs a two-turn chat with a one-node calculator chatbot. The chatbot's model is a scripted fake, so the run needs no API key and no network. Then it calls the `add_messages` reducer by hand to show how it appends, replaces and removes messages, and compares it with `operator.add`. Run it with `./run.sh 4.1` from the course root.
The concept itself is explained in the [notes](notes.md).

This lesson starts the calculator-agent example. 4.2 adds tools to it, and 4.3 rebuilds it with `create_agent`.

## [chatbot.py](../src/l4_1_messages_state/chatbot.py)

The graph and its model: a system prompt, a factory for the fake model, and a one-node graph over `MessagesState`.

- The imports on [line 6](../src/l4_1_messages_state/chatbot.py#L6) take `MessagesState` from `langgraph.graph`. It is a ready-made `TypedDict` with one key, `messages: Annotated[list[AnyMessage], add_messages]`. Writing that class yourself would give the same state. There is no state class in this lesson because the built-in one is all the chatbot needs.
- [`SYSTEM_PROMPT`](../src/l4_1_messages_state/chatbot.py#L11) is a plain module constant, not part of the state. The fake model ignores it, but a real model would read it, so the node is written exactly as it would be for a real provider.

### The fake model

- [`make_model`](../src/l4_1_messages_state/chatbot.py#L16-L26) returns a `GenericFakeChatModel` from langchain-core. It is a real `BaseChatModel`: `invoke`, callbacks and message ids all work as with a provider model. Only the generation step is scripted: each call takes `next(...)` from the iterator and wraps a string in an `AIMessage`. It never looks at the messages it receives.
  - Line 26 wraps the list in `iter(...)`. The field is typed `Iterator`, so pydantic rejects a plain list. Because an iterator can be read only once, a model built for one run cannot be reused: its third call in a two-reply script fails, as the docstring says.
  - The model is built in its own function, and `build_graph` receives it as an argument. 4.2 replaces this function with a fake that supports `bind_tools` (this one raises `NotImplementedError` for it). The tests also call it to get a fresh model for each test.

### The node and the graph

- [`build_graph`](../src/l4_1_messages_state/chatbot.py#L33-L56) takes the model and defines the node inside it. [`call_model`](../src/l4_1_messages_state/chatbot.py#L41-L47) is a closure: it uses `model` from the enclosing function, so the node's signature can stay `(state)`, the form LangGraph calls nodes with.
  - Line 44 builds the model's input as a new list: a `SystemMessage` followed by the conversation from state. The system message exists only for this call. It is never returned, so it never reaches the state, and the output of the run contains only human and AI messages. [`test_two_turn_chat`](../tests/test_messages_state.py#L16-L30) checks this on line 24.
  - Line 47 returns only the reply, in a one-element list. LangGraph passes it to `add_messages(current_messages, [reply])`, which appends it because its id is new. The reply's id comes from langchain-core, which sets it to `lc_run--` plus the run id when the model is called.
  - The `MessagesState` hint on line 41 is not just documentation. LangGraph reads a node's state hint as the node's input schema and registers its channels too. If the graph were built on a different class with its own `messages` key, `add_node` would already fail (before `compile()`) with "Channel 'messages' already exists with a different type". That is why `build_graph` is not parametrized by the state class.
- Line 52, `StateGraph(MessagesState)`, is where `add_messages` gets attached to the `messages` channel. Lines 53–55 wire one node in a straight line, `START -> call_model -> END`.
- Line 56 compiles without a checkpointer. Each `invoke` starts with an empty `messages` channel and forgets everything when it returns. The caller has to carry the history, which is what `main` does in turn 2. Lesson 5.1 adds a checkpointer so the graph remembers on its own.

## [\_\_main\_\_.py](../src/l4_1_messages_state/__main__.py)

The entry point. [`main`](../src/l4_1_messages_state/__main__.py#L23-L65) runs the chat first, then calls the reducer directly.

- [`show`](../src/l4_1_messages_state/__main__.py#L11-L14) prints the class name of each message, which is how the output shows that a tuple became a `HumanMessage`. [`show_ids`](../src/l4_1_messages_state/__main__.py#L17-L20) also prints the id, and is used only in the second section, where the ids are short fixed strings. The ids from the graph run are random uuids, so printing them would change the output on every run.

### A two-turn chat

- Line 27 scripts two replies, one per turn. A third `invoke` on the same graph would run out of replies.
- Line 34, turn 1: the input is `("user", "What is 2 + 3?")`, a tuple, not a message. The input goes into the `messages` channel through the reducer like any node update, so it becomes `add_messages([], [("user", ...)])`. `add_messages` converts the tuple to a `HumanMessage` and gives it a uuid id. Only then does `call_model` run, so the node already sees a proper message. Line 36 prints `True` because both messages have ids.
- Line 40, turn 2: the input is the whole turn-1 history plus a new tuple. The channel starts empty again (no checkpointer), so all three are appended, and the reply makes four. The two old messages already have ids, and `add_messages` assigns ids only to messages without one. So their ids stay the same, which line 42 checks. Turn 2 works only because line 40 passes the history back in. Without it, the model would see only "And times 4?".

### add_messages is a plain function

- [Lines 47–65](../src/l4_1_messages_state/__main__.py#L47-L65) call `add_messages` (imported from `langgraph.graph` on line 6) with two lists, exactly as the graph does on each write. Line 50 builds a `history` with fixed ids `q1` and `a1` and a wrong answer to correct.
- Each call starts from the same `history`, not from the previous result. That is why the "remove q1" output shows `a1` with the original wrong text `2 + 3 is 6.`: the fix from the line before was never stored anywhere.
  - Line 53: `q2` is not in the history, so it is appended at the end.
  - Line 56: `a1` is already there, so the new message takes its place, in position 2. The length stays 2. This is how a node fixes or updates a message: it returns a message with the same id.
  - Line 59: a `RemoveMessage` is not added to the list. It marks the message with its id for deletion. The id must exist: an unknown id raises `ValueError` ([`test_remove_unknown_id_raises`](../tests/test_messages_state.py#L55-L58)).
  - Line 62: `operator.add` is plain list concatenation, `history + [...]`. It does not look at ids, so `a1` appears twice. This is what a hand-written `messages` key with `operator.add` would store.
- Line 65 prints 2. `add_messages` copies the left list before merging and returns the copy, so the list a caller passes in is never changed.

## [test_messages_state.py](../tests/test_messages_state.py)

The tests check the live run's results and two graph cases that `main` does not show.

- [`make_history`](../tests/test_messages_state.py#L11-L13) returns new message objects on each call. [`test_add_messages_direct`](../tests/test_messages_state.py#L33-L52) uses it on line 52 to compare `history` with a fresh copy after four reducer calls.
- [`test_add_messages_inside_graph`](../tests/test_messages_state.py#L61-L84) runs the reducer inside real graphs:
  - [`return_full_state`](../tests/test_messages_state.py#L64-L66) returns the whole history plus a reply, a common mistake. With `add_messages` it is harmless: the old message's id is already in state, so it is replaced by itself, and line 73 sees 2 messages, not 3. With an `operator.add` key, the history would be duplicated.
  - [`remove_first`](../tests/test_messages_state.py#L75-L77) reads the id from state instead of guessing it, then returns a `RemoveMessage` for it. Line 84 shows that only `a1` is left.
- [`test_script_consumed_once`](../tests/test_messages_state.py#L87-L97) builds one model with two replies and calls the graph three times. The third call raises `RuntimeError` (line 96). The fake model's `next()` raises `StopIteration`, which escapes through LangGraph's `Pregel.stream` generator (the one `invoke` iterates), so Python turns it into `RuntimeError: generator raised StopIteration`. Calling the model directly would raise the bare `StopIteration`, as the `make_model` docstring says.

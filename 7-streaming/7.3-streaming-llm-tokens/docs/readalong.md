# 7.3 Streaming LLM Tokens — code walkthrough

The program runs the same order through the pick, pack and ship graph from 7.2. A new last node, `confirm`, calls a chat model three times: once for a customer email, once for an SMS and once for a warehouse note. The program reads the model's tokens five ways: all of them with `stream_mode="messages"`, next to the updates in `version="v2"`, filtered by node, filtered by tag, and with the `nostream` call left out. Run it with `./run.sh 7.3` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 7.2

`pick`, `pack`, `ship`, `ORDER` and the `values`, `updates` and `custom` cases of `describe` are the same as in 7.2. For those, see the [7.2 walkthrough](../../7.2-custom-stream-data/docs/readalong.md).

- [pyproject.toml](../pyproject.toml#L6) now also depends on `langchain-core==1.6.12`, because the lesson imports the fake chat model from it directly.
- [orders.py](../src/l7_3_streaming_llm_tokens/orders.py#L9-L11) imports `GenericFakeChatModel` and `TAG_NOSTREAM`.
- [`OrderState`](../src/l7_3_streaming_llm_tokens/orders.py#L30-L32) has three new keys: `email`, `sms` and `note`.
- [`chat_model`](../src/l7_3_streaming_llm_tokens/orders.py#L85-L90) is a new helper that builds the fake model.
- [`confirm`](../src/l7_3_streaming_llm_tokens/orders.py#L97-L120) is the new node that calls the model.
- [`build_graph`](../src/l7_3_streaming_llm_tokens/orders.py#L133-L139) adds `confirm` and the edges `ship -> confirm -> END` in place of `ship -> END`.
- [`describe`](../src/l7_3_streaming_llm_tokens/render.py#L38-L41) has a new `case "messages"` above the fallback.
- [\_\_main\_\_.py](../src/l7_3_streaming_llm_tokens/__main__.py#L16-L83) replaces the four sections of 7.2 with five new ones. It no longer imports `Runtime`, `pack` and `ship`.
- [test_streaming_llm_tokens.py](../tests/test_streaming_llm_tokens.py) replaces `test_custom_stream_data.py`.

## [orders.py](../src/l7_3_streaming_llm_tokens/orders.py)

The state, the nodes and the graph. The new part is a node that calls a chat model.

- [Line 9](../src/l7_3_streaming_llm_tokens/orders.py#L9) imports `GenericFakeChatModel`, the same fake model as in [lesson 4.1](../../../4-agents/4.1-messages-state/docs/readalong.md). It needs no API key, works offline and gives the same reply every run, so the output and the tests stay deterministic.
- [Line 11](../src/l7_3_streaming_llm_tokens/orders.py#L11) imports `TAG_NOSTREAM` from `langgraph.constants`. Its value is the plain string `"nostream"`. LangGraph checks for exactly that string, so a typo such as `"no-stream"` would quietly do nothing. With the constant, a typo becomes a `NameError` (experiment 3).
- The new keys of [`OrderState`](../src/l7_3_streaming_llm_tokens/orders.py#L30-L32) are plain `str`, not messages. That matters for `note`, as `confirm` explains below.
- [`pack`](../src/l7_3_streaming_llm_tokens/orders.py#L48-L62) and [`ship`](../src/l7_3_streaming_llm_tokens/orders.py#L65-L74) still write their progress. None of the runs in this lesson asks for `"custom"`, so they get the do-nothing writer from 7.2 and the progress is dropped.

### [`chat_model`](../src/l7_3_streaming_llm_tokens/orders.py#L85-L90)

- `GenericFakeChatModel` takes its replies from `messages`, an iterator, and returns the next one on each call, whatever the prompt is. `iter([reply])` on [line 90](../src/l7_3_streaming_llm_tokens/orders.py#L90) holds one reply. A second call on the same model would find the iterator empty and fail. That is why `confirm` builds a new model for every call, while a real app would create its model once.
- When it streams, the fake model splits the reply at whitespace and keeps each space as a separate chunk. That is why the output shows `' '` lines between the words. A real provider splits its output in other places.
- `tags=tags` sets the standard `tags` field that every LangChain chat model has. LangChain passes these tags to the callbacks of each call, and LangGraph copies them into the metadata of each token. The caller uses them to tell the calls apart.

### [`confirm`](../src/l7_3_streaming_llm_tokens/orders.py#L97-L120)

- All three calls on [lines 106-116](../src/l7_3_streaming_llm_tokens/orders.py#L106-L116) use `.invoke()`, and the email and SMS still arrive token by token. When the caller asks for `"messages"`, LangGraph adds its own callback handler (`StreamMessagesHandler`) to the run's config. The chat model sees a streaming handler among its callbacks and generates the reply in chunks, even inside `invoke()`. The handler forwards each chunk to the stream. `invoke()` then joins the chunks and returns one complete `AIMessage` to the node. Without `"messages"` there is no such handler, and `invoke()` generates the whole reply at once.
- The node itself does nothing special for streaming. The model picks up the run's callbacks on its own, because LangGraph passes the run config to it through the context.
- The note call on [line 114](../src/l7_3_streaming_llm_tokens/orders.py#L114) is tagged `TAG_NOSTREAM`. When a model call starts, the handler skips any call with this tag, so none of its tokens reach the stream. The call still runs, and its reply is still returned to `confirm`.
- [Line 120](../src/l7_3_streaming_llm_tokens/orders.py#L120) stores `.text`, the content as a string, in the state. `.text` is a property, so there are no parentheses. Storing strings matters: messages mode also emits message objects that a node returns in its update, and `nostream` does not stop those. If `note` held the `AIMessage`, the note text would show up in the stream after all (experiment 5).
- `confirm` does not need a running graph. Unlike `pack` in 7.2, whose `get_stream_writer()` raises `RuntimeError` outside a run, it does not *need* a run context: outside a graph the models simply find no streaming handler and do not stream. So the tests call it directly.

### [`build_graph`](../src/l7_3_streaming_llm_tokens/orders.py#L127-L140)

- [Line 133](../src/l7_3_streaming_llm_tokens/orders.py#L133) registers `confirm`, and [lines 138-139](../src/l7_3_streaming_llm_tokens/orders.py#L138-L139) put it after `ship`. The graph stays linear, so `confirm` runs in its own super-step after the other three. That is why all the tokens arrive after `ship`'s update.

## [render.py](../src/l7_3_streaming_llm_tokens/render.py)

`describe` turns one v2 part into a line of text. It has one new case.

- The `case "messages"` on [lines 38-41](../src/l7_3_streaming_llm_tokens/render.py#L38-L41) handles one token. In v2, `data` is the same `(chunk, metadata)` pair that v1 yields directly, so [line 40](../src/l7_3_streaming_llm_tokens/render.py#L40) unpacks it. The line shows the node from `metadata["langgraph_node"]` and the chunk text with `!r`, so that the space chunks are visible as `' '`.
- The fallback `case other` on [lines 42-44](../src/l7_3_streaming_llm_tokens/render.py#L42-L44) stays. It still catches the part types that the lesson does not show.

## [\_\_main\_\_.py](../src/l7_3_streaming_llm_tokens/__main__.py)

The live run. [`ORDER`](../src/l7_3_streaming_llm_tokens/__main__.py#L13) is the same input as in 7.2. [`main`](../src/l7_3_streaming_llm_tokens/__main__.py#L16-L83) builds the graph once and runs it six times: once in each section, and once more with `invoke()` in the last one. Every run calls the model again, and since `confirm` builds new fake models each time, every run gets the same replies.

### All tokens ([lines 20-33](../src/l7_3_streaming_llm_tokens/__main__.py#L20-L33))

- With the single mode `"messages"` in v1, the loop on [line 30](../src/l7_3_streaming_llm_tokens/__main__.py#L30) gets one `(AIMessageChunk, metadata)` tuple per token: nine for the email, three for the SMS, none for the note. `pick`, `pack` and `ship` call no model, so they produce nothing in this mode.
- `metadata` is a dict that LangGraph builds for each call. It always has `langgraph_node`, the node that made the call, along with `langgraph_step`, `langgraph_triggers` and a few others. [Line 31](../src/l7_3_streaming_llm_tokens/__main__.py#L31) indexes `langgraph_node` directly but reads `tags` with `.get`. LangGraph adds `"tags"` only when the call has tags you set, so for an untagged call the key does not exist and `metadata["tags"]` raises `KeyError` (experiment 4).
- LangGraph emits each token once. When a call ends, the handler would also emit the complete message, but it skips it because it has the same id as the chunks it already sent. So there are exactly 12 items and no extra full message.

### Tokens next to the updates ([lines 35-44](../src/l7_3_streaming_llm_tokens/__main__.py#L35-L44))

- The call on [line 41](../src/l7_3_streaming_llm_tokens/__main__.py#L41) asks for `"updates"` and `"messages"` in v2. Each item is a dict with `type`, `ns` and `data`, and `describe` formats it.
- The 12 messages parts come after `ship`'s update and before `confirm`'s update. The tokens are sent while `confirm` is still running, and its update exists only after it returns. As with `"custom"` in 7.2, asking for `"messages"` turns on eager streaming, so each token reaches the caller as soon as the model yields it.

### Filtered by node ([lines 46-59](../src/l7_3_streaming_llm_tokens/__main__.py#L46-L59))

- The loop prints each chunk with `end=""` and `flush=True` ([line 56](../src/l7_3_streaming_llm_tokens/__main__.py#L56)), so the text appears on one line as it arrives, which is how a chat UI types a reply out.
- The filter on [line 55](../src/l7_3_streaming_llm_tokens/__main__.py#L55) keeps tokens from `confirm`. Both visible calls run in `confirm`, so the email and the SMS run together into `...TRK-A-1001.Shipped: TRK-A-1001`. The node filter is enough only when each node makes one model call.

### Filtered by tag ([lines 61-71](../src/l7_3_streaming_llm_tokens/__main__.py#L61-L71))

- The filter on [line 67](../src/l7_3_streaming_llm_tokens/__main__.py#L67) picks a single call by its tag, wherever it runs. It uses `in` because a call can have several tags, and `.get("tags", [])` because untagged calls have no `"tags"` key. Only the email is printed.

### The nostream call ([lines 73-84](../src/l7_3_streaming_llm_tokens/__main__.py#L73-L84))

- [Lines 79-81](../src/l7_3_streaming_llm_tokens/__main__.py#L79-L81) collect every tag seen in the token stream. The result is `['email', 'sms']`, so no token of the `nostream` call was streamed.
- [Line 83](../src/l7_3_streaming_llm_tokens/__main__.py#L83) runs the graph again with `invoke()` and prints `note` from the final state. The text is there. `nostream` hides a call from messages mode, but the call itself still runs.

## [test_streaming_llm_tokens.py](../tests/test_streaming_llm_tokens.py)

The tests import `ORDER` from `__main__`, so they use the same input as the live run. [`EMAIL`, `SMS` and `NOTE`](../tests/test_streaming_llm_tokens.py#L10-L12) are the three scripted replies, and [`SECTION_B`](../tests/test_streaming_llm_tokens.py#L14-L32) holds the 16 lines of the second section.

- [`_messages`](../tests/test_streaming_llm_tokens.py#L35-L37) collects the v1 pairs. [`_v2_parts`](../tests/test_streaming_llm_tokens.py#L40-L44) collects the v2 parts and turns every warning into an error, as in 7.2.
- [`test_messages_mode_streams_only_tagged_confirm_calls`](../tests/test_streaming_llm_tokens.py#L47-L55) checks section (a): 12 chunks, all `AIMessageChunk`, all from `confirm`, nine `['email']` followed by three `['sms']`. It compares the joined text of each call, not single chunks, because chunk boundaries depend on the model.
- [`test_tokens_arrive_between_the_updates_in_v2`](../tests/test_streaming_llm_tokens.py#L58-L66) checks the type sequence of section (b), the three keys and `ns == ()` of every messages part, and `confirm`'s final update.
- [`test_node_filter_mixes_calls_tag_filter_separates_them`](../tests/test_streaming_llm_tokens.py#L69-L75) checks sections (c) and (d) on the joined text.
- [`test_nostream_keeps_note_out_of_stream_not_out_of_state`](../tests/test_streaming_llm_tokens.py#L78-L97) checks section (e) and the full final state. [Lines 96-97](../tests/test_streaming_llm_tokens.py#L96-L97) call `confirm` directly, without a graph, and get the same three values.
- [`test_describe_renders_messages_and_keeps_fallback`](../tests/test_streaming_llm_tokens.py#L100-L105) checks the printed lines of section (b) and the fallback with a hand-made `"tasks"` part.

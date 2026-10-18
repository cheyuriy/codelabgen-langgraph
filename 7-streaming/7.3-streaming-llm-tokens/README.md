# 7.3 Streaming LLM Tokens

Adds a node that writes a shipping confirmation with a fake chat model that streams chunk by chunk. Uses stream_mode="messages", filters tokens by node via metadata and by tags, and keeps a model silent with nostream.

> [!NOTE]
> This lesson continues the example from [7.2 Custom Progress Events with get_stream_writer](../7.2-custom-stream-data/README.md).

## What you will learn

- Stream tokens from a chat model inside a node with stream_mode="messages"
- Filter message chunks by langgraph_node metadata or by tags
- Exclude a model call from the token stream

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l7_3_streaming_llm_tokens/__main__.py), [orders.py](src/l7_3_streaming_llm_tokens/orders.py), [render.py](src/l7_3_streaming_llm_tokens/render.py)

## How to run

From the course root:

```bash
./run.sh 7.3
```

Or by hand:

```bash
cd 7-streaming && uv sync --all-packages --quiet
cd 7.3-streaming-llm-tokens
uv run --package l7-3-streaming-llm-tokens python -m l7_3_streaming_llm_tokens
```

Run the tests:

```bash
./run.sh test 7.3
```

← Previous: [7.2 Custom Progress Events with get_stream_writer](../7.2-custom-stream-data/README.md) · Next: [7.4 Event Streaming with stream_events v3](../7.4-event-streaming/README.md) →

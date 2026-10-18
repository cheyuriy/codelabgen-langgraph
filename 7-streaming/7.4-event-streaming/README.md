# 7.4 Event Streaming with stream_events v3

Consumes the same run through stream_events(version="v3"): a run stream object with typed projections for values, messages and the final output, compared with the stream-mode API.

> [!NOTE]
> This lesson continues the example from [7.3 Streaming LLM Tokens](../7.3-streaming-llm-tokens/README.md).

## What you will learn

- Start a run with stream_events(version="v3") and iterate its projections
- Read the final output and state values from the run stream
- Decide between stream modes and event streaming for a given client

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l7_4_event_streaming/__main__.py), [orders.py](src/l7_4_event_streaming/orders.py)

## How to run

From the course root:

```bash
./run.sh 7.4
```

Or by hand:

```bash
cd 7-streaming && uv sync --all-packages --quiet
cd 7.4-event-streaming
uv run --package l7-4-event-streaming python -m l7_4_event_streaming
```

Run the tests:

```bash
./run.sh test 7.4
```

← Previous: [7.3 Streaming LLM Tokens](../7.3-streaming-llm-tokens/README.md) · Next: [8.1 Subgraphs with Shared State](../../8-multi-agent/8.1-subgraphs-shared-state/README.md) →

# 7.2 Custom Progress Events with get_stream_writer

The packing node reports per-item progress with get_stream_writer, and the caller prints it from stream_mode="custom" next to the regular updates.

> [!NOTE]
> This lesson continues the example from [7.1 Stream Modes: values, updates and Typed v2 Parts](../7.1-stream-modes/README.md).

## What you will learn

- Emit custom data from inside a node with get_stream_writer
- Receive custom chunks alongside updates and render them as progress
- Explain when custom events are better than writing progress into the state

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l7_2_custom_stream_data/__main__.py), [orders.py](src/l7_2_custom_stream_data/orders.py), [render.py](src/l7_2_custom_stream_data/render.py)

## How to run

From the course root:

```bash
./run.sh 7.2
```

Or by hand:

```bash
cd 7-streaming && uv sync --all-packages --quiet
cd 7.2-custom-stream-data
uv run --package l7-2-custom-stream-data python -m l7_2_custom_stream_data
```

Run the tests:

```bash
./run.sh test 7.2
```

← Previous: [7.1 Stream Modes: values, updates and Typed v2 Parts](../7.1-stream-modes/README.md) · Next: [7.3 Streaming LLM Tokens](../7.3-streaming-llm-tokens/README.md) →

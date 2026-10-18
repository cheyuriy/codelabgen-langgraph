# 7.1 Stream Modes: values, updates and Typed v2 Parts

Streams an order-fulfilment graph (pick, pack, ship) with stream_mode values and updates, then several modes at once, and switches to version="v2" so every chunk is a typed StreamPart with type, ns and data.

## What you will learn

- Choose between stream_mode="values" and "updates" and read what each yields
- Combine several stream modes in one call and tell the chunks apart
- Consume version="v2" StreamPart dicts instead of bare tuples

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l7_1_stream_modes/__main__.py), [orders.py](src/l7_1_stream_modes/orders.py), [render.py](src/l7_1_stream_modes/render.py)

## How to run

From the course root:

```bash
./run.sh 7.1
```

Or by hand:

```bash
cd 7-streaming && uv sync --all-packages --quiet
cd 7.1-stream-modes
uv run --package l7-1-stream-modes python -m l7_1_stream_modes
```

Run the tests:

```bash
./run.sh test 7.1
```

← Previous: [6.5 Time Travel: History, Replay and Forks](../../6-human-in-the-loop/6.5-time-travel/README.md) · Next: [7.2 Custom Progress Events with get_stream_writer](../7.2-custom-stream-data/README.md) →

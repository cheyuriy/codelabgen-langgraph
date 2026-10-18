# 8.1 Subgraphs with Shared State

A support desk graph adds a compiled billing subgraph directly as a node; parent and subgraph communicate through shared keys. Shows get_graph(xray=True) and streaming with subgraphs=True to see namespaced updates.

## What you will learn

- Add a compiled graph as a node when parent and subgraph share state keys
- Inspect nested structure with get_graph(xray=True) and stream subgraph updates with subgraphs=True
- Explain how the parent's checkpointer is propagated to the subgraph

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l8_1_subgraphs_shared_state/__main__.py), [billing.py](src/l8_1_subgraphs_shared_state/billing.py), [desk.py](src/l8_1_subgraphs_shared_state/desk.py), [show.py](src/l8_1_subgraphs_shared_state/show.py)

## How to run

From the course root:

```bash
./run.sh 8.1
```

Or by hand:

```bash
cd 8-multi-agent && uv sync --all-packages --quiet
cd 8.1-subgraphs-shared-state
uv run --package l8-1-subgraphs-shared-state python -m l8_1_subgraphs_shared_state
```

Run the tests:

```bash
./run.sh test 8.1
```

← Previous: [7.4 Event Streaming with stream_events v3](../../7-streaming/7.4-event-streaming/README.md) · Next: [8.2 Subgraphs with Their Own State](../8.2-subgraphs-own-state/README.md) →

# 5.4 Long-Term Memory with a Store

A reading-list assistant remembers a user's favourite genres across threads with InMemoryStore: namespaces per user, put, get and search, and runtime.store inside nodes, next to the per-thread checkpointer.

## What you will learn

- Explain the difference between thread-scoped checkpoints and cross-thread stores
- Save and read memories with put, get and search in a namespace tied to the user
- Access the store from a node through the runtime and pass the user id via context

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l5_4_long_term_memory_store/__main__.py), [assistant.py](src/l5_4_long_term_memory_store/assistant.py)

## How to run

From the course root:

```bash
./run.sh 5.4
```

Or by hand:

```bash
cd 5-persistence && uv sync --all-packages --quiet
cd 5.4-long-term-memory-store
uv run --package l5-4-long-term-memory-store python -m l5_4_long_term_memory_store
```

Run the tests:

```bash
./run.sh test 5.4
```

← Previous: [5.3 Trimming and Summarizing Message History](../5.3-message-history/README.md) · Next: [5.5 Semantic Search over Memories](../5.5-semantic-memory-search/README.md) →

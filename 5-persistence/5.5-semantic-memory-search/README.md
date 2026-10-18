# 5.5 Semantic Search over Memories

Gives the store an embedding index so the assistant finds memories by meaning rather than by key. Uses a deterministic fake embedding so search results are reproducible offline.

> [!NOTE]
> This lesson continues the example from [5.4 Long-Term Memory with a Store](../5.4-long-term-memory-store/README.md).

## What you will learn

- Configure InMemoryStore with an index (dims and embed) and choose which fields are embedded
- Retrieve relevant memories with search(query=...) and read their scores
- Explain how semantic memory differs from keyed lookups and when each fits

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l5_5_semantic_memory_search/__main__.py), [assistant.py](src/l5_5_semantic_memory_search/assistant.py)

## How to run

From the course root:

```bash
./run.sh 5.5
```

Or by hand:

```bash
cd 5-persistence && uv sync --all-packages --quiet
cd 5.5-semantic-memory-search
uv run --package l5-5-semantic-memory-search python -m l5_5_semantic_memory_search
```

Run the tests:

```bash
./run.sh test 5.5
```

← Previous: [5.4 Long-Term Memory with a Store](../5.4-long-term-memory-store/README.md) · Next: [5.6 Postgres Checkpointer and Store for Production](../5.6-postgres-persistence/README.md) →

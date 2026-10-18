# 5.1 Checkpointers and Threads

Starts from a compact copy of the calculator agent and adds InMemorySaver, so it remembers earlier turns within a thread_id and starts fresh in another. Shows get_state and the StateSnapshot it returns.

## What you will learn

- Compile a graph with a checkpointer and keep separate conversations by thread_id
- Inspect the latest saved state with get_state and read its values, next and config
- Explain what a checkpoint is and when it is written

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l5_1_checkpointers_and_threads/__main__.py), [chatbot.py](src/l5_1_checkpointers_and_threads/chatbot.py), [tools.py](src/l5_1_checkpointers_and_threads/tools.py)

## How to run

From the course root:

```bash
./run.sh 5.1
```

Or by hand:

```bash
cd 5-persistence && uv sync --all-packages --quiet
cd 5.1-checkpointers-and-threads
uv run --package l5-1-checkpointers-and-threads python -m l5_1_checkpointers_and_threads
```

Run the tests:

```bash
./run.sh test 5.1
```

← Previous: [4.3 The Prebuilt Agent with create_agent](../../4-agents/4.3-create-agent/README.md) · Next: [5.2 Durable Checkpoints with SQLite](../5.2-sqlite-checkpointer/README.md) →

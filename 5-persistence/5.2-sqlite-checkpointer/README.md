# 5.2 Durable Checkpoints with SQLite

Swaps InMemorySaver for SqliteSaver so a conversation survives a process restart: the run is executed twice as separate processes on the same database file. Covers from_conn_string and the durability modes (exit, async, sync).

> [!NOTE]
> This lesson continues the example from [5.1 Checkpointers and Threads](../5.1-checkpointers-and-threads/README.md).

## What you will learn

- Persist checkpoints in a file with SqliteSaver and resume a thread in a new process
- Choose a durability mode and explain its cost and safety trade-off
- Recognise the thread_id and serialization rules that persistent checkpointers impose

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l5_2_sqlite_checkpointer/__main__.py), [chatbot.py](src/l5_2_sqlite_checkpointer/chatbot.py), [tools.py](src/l5_2_sqlite_checkpointer/tools.py)

## How to run

From the course root:

```bash
./run.sh 5.2
```

Or by hand:

```bash
cd 5-persistence && uv sync --all-packages --quiet
cd 5.2-sqlite-checkpointer
uv run --package l5-2-sqlite-checkpointer python -m l5_2_sqlite_checkpointer
```

Run the tests:

```bash
./run.sh test 5.2
```

← Previous: [5.1 Checkpointers and Threads](../5.1-checkpointers-and-threads/README.md) · Next: [5.3 Trimming and Summarizing Message History](../5.3-message-history/README.md) →

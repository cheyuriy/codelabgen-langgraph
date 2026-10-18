# 5.3 Trimming and Summarizing Message History

Keeps a long conversation small: trims what is sent to the model with trim_messages, deletes old messages from state with RemoveMessage, and folds them into a running summary kept in the state.

> [!NOTE]
> This lesson continues the example from [5.2 Durable Checkpoints with SQLite](../5.2-sqlite-checkpointer/README.md).

## What you will learn

- Limit what the model sees with trim_messages without changing the saved state
- Delete old messages from the checkpointed state by returning RemoveMessage updates
- Add a summarization step that runs only when the history passes a threshold

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__init__.py](src/l5_3_message_history/__init__.py), [__main__.py](src/l5_3_message_history/__main__.py), [chatbot.py](src/l5_3_message_history/chatbot.py), [tools.py](src/l5_3_message_history/tools.py)

## How to run

From the course root:

```bash
./run.sh 5.3
```

Or by hand:

```bash
cd 5-persistence && uv sync --all-packages --quiet
cd 5.3-message-history
uv run --package l5-3-message-history python -m l5_3_message_history
```

Run the tests:

```bash
./run.sh test 5.3
```

← Previous: [5.2 Durable Checkpoints with SQLite](../5.2-sqlite-checkpointer/README.md) · Next: [5.4 Long-Term Memory with a Store](../5.4-long-term-memory-store/README.md) →

# 4.1 Messages in State and an Offline Chat Model

Builds a one-node chatbot on MessagesState with a scripted fake chat model so it runs offline. Explains add_messages: appending, merging by message id, and deleting with RemoveMessage, compared with plain list concatenation.

## What you will learn

- Keep a conversation in state with MessagesState and the add_messages reducer
- Call a chat model from a node, using a fake model so tests and runs need no API key
- Show how add_messages replaces a message with the same id and removes one with RemoveMessage

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l4_1_messages_state/__main__.py), [chatbot.py](src/l4_1_messages_state/chatbot.py)

## How to run

From the course root:

```bash
./run.sh 4.1
```

Or by hand:

```bash
cd 4-agents && uv sync --all-packages --quiet
cd 4.1-messages-state
uv run --package l4-1-messages-state python -m l4_1_messages_state
```

Run the tests:

```bash
./run.sh test 4.1
```

← Previous: [3.3 Command: Update State and Route in One Step](../../3-control-flow/3.3-command/README.md) · Next: [4.2 A Tool-Calling Agent Loop by Hand](../4.2-tool-calling-loop/README.md) →

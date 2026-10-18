# 6.5 Time Travel: History, Replay and Forks

Walks back through the refund thread with get_state_history, replays from an earlier checkpoint, and forks it with update_state (including as_node) to try a different decision, comparing replay with fork.

> [!NOTE]
> This lesson continues the example from [6.2 Approve, Edit and Validate: Interrupt Patterns](../6.2-interrupt-patterns/README.md).

## What you will learn

- List a thread's checkpoints with get_state_history and pick one by checkpoint_id
- Replay a run from an earlier checkpoint and explain which nodes run again
- Fork a thread by changing past state with update_state and continue from the fork

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l6_5_time_travel/__main__.py), [refunds.py](src/l6_5_time_travel/refunds.py)

## How to run

From the course root:

```bash
./run.sh 6.5
```

Or by hand:

```bash
cd 6-human-in-the-loop && uv sync --all-packages --quiet
cd 6.5-time-travel
uv run --package l6-5-time-travel python -m l6_5_time_travel
```

Run the tests:

```bash
./run.sh test 6.5
```

← Previous: [6.4 Approving Tool Calls Inside an Agent](../6.4-interrupts-in-tools/README.md) · Next: [7.1 Stream Modes: values, updates and Typed v2 Parts](../../7-streaming/7.1-stream-modes/README.md) →

# 6.1 Pausing with interrupt() and Resuming with Command

A refund request above a limit pauses for a manager's decision. Shows interrupt() with a payload, why a checkpointer and thread_id are required, reading the pending interrupt (v1 __interrupt__ and v2 GraphOutput.interrupts), and resuming with Command(resume=...).

## What you will learn

- Pause a node with interrupt() and surface a payload to the caller
- Resume the paused thread with Command(resume=value) and use the value in the node
- Read pending interrupts from invoke output in both v1 and v2 formats and from get_state

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l6_1_interrupt_and_resume/__main__.py), [refunds.py](src/l6_1_interrupt_and_resume/refunds.py)

## How to run

From the course root:

```bash
./run.sh 6.1
```

Or by hand:

```bash
cd 6-human-in-the-loop && uv sync --all-packages --quiet
cd 6.1-interrupt-and-resume
uv run --package l6-1-interrupt-and-resume python -m l6_1_interrupt_and_resume
```

Run the tests:

```bash
./run.sh test 6.1
```

← Previous: [5.6 Postgres Checkpointer and Store for Production](../../5-persistence/5.6-postgres-persistence/README.md) · Next: [6.2 Approve, Edit and Validate: Interrupt Patterns](../6.2-interrupt-patterns/README.md) →

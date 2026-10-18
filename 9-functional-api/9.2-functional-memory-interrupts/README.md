# 9.2 Functional API: Memory, Interrupts and Determinism

Adds an approval interrupt and a running order count. On resume the entrypoint replays from the start but finished tasks return their saved results; shows previous, entrypoint.final, and why side effects belong in tasks.

> [!NOTE]
> This lesson continues the example from [9.1 @entrypoint and @task](../9.1-entrypoint-and-task/README.md).

## What you will learn

- Keep values between runs of a thread with the previous parameter and entrypoint.final
- Pause an entrypoint with interrupt() and resume it, observing that completed tasks are not re-executed
- Keep entrypoint code deterministic by moving side effects and randomness into tasks

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__init__.py](src/l9_2_functional_memory_interrupts/__init__.py), [__main__.py](src/l9_2_functional_memory_interrupts/__main__.py), [workflow.py](src/l9_2_functional_memory_interrupts/workflow.py)

## How to run

From the course root:

```bash
./run.sh 9.2
```

Or by hand:

```bash
cd 9-functional-api && uv sync --all-packages --quiet
cd 9.2-functional-memory-interrupts
uv run --package l9-2-functional-memory-interrupts python -m l9_2_functional_memory_interrupts
```

Run the tests:

```bash
./run.sh test 9.2
```

← Previous: [9.1 @entrypoint and @task](../9.1-entrypoint-and-task/README.md) · Next: [10.1 Retry and Cache Policies](../../10-production/10.1-retry-and-cache/README.md) →

# 10.4 Recovering a Failed Run

A run fails mid-way after some nodes have finished. With a checkpointer the finished work is kept (including pending writes of parallel siblings), the cause is fixed, and the run resumes with invoke(None) on the same thread.

> [!NOTE]
> This lesson continues the example from [10.3 Error Handlers and Node Defaults](../10.3-error-handlers/README.md).

## What you will learn

- Resume a failed run from its last checkpoint by invoking with None on the same thread_id
- Show that successful parallel siblings are not re-executed thanks to pending writes
- Relate durability modes to how much work survives a crash

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l10_4_recover_failed_run/__main__.py), [graph.py](src/l10_4_recover_failed_run/graph.py), [service.py](src/l10_4_recover_failed_run/service.py)

## How to run

From the course root:

```bash
./run.sh 10.4
```

Or by hand:

```bash
cd 10-production && uv sync --all-packages --quiet
cd 10.4-recover-failed-run
uv run --package l10-4-recover-failed-run python -m l10_4_recover_failed_run
```

Run the tests:

```bash
./run.sh test 10.4
```

← Previous: [10.3 Error Handlers and Node Defaults](../10.3-error-handlers/README.md) · Next: [10.5 Testing Graphs with pytest](../10.5-testing-graphs/README.md) →

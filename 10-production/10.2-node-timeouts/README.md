# 10.2 Node Timeouts

Puts a timeout on the slow rate lookup: a hard timeout raises NodeTimeoutError, a TimeoutPolicy with an idle timeout lets a long node stay alive by calling runtime.heartbeat(), and timeouts combine with retries.

> [!NOTE]
> This lesson continues the example from [10.1 Retry and Cache Policies](../10.1-retry-and-cache/README.md).

## What you will learn

- Set a per-node timeout and handle NodeTimeoutError
- Use TimeoutPolicy with an idle timeout and keep a long-running node alive with heartbeats
- Combine a timeout with a retry policy and predict the number of attempts

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l10_2_node_timeouts/__main__.py), [graph.py](src/l10_2_node_timeouts/graph.py), [service.py](src/l10_2_node_timeouts/service.py)

## How to run

From the course root:

```bash
./run.sh 10.2
```

Or by hand:

```bash
cd 10-production && uv sync --all-packages --quiet
cd 10.2-node-timeouts
uv run --package l10-2-node-timeouts python -m l10_2_node_timeouts
```

Run the tests:

```bash
./run.sh test 10.2
```

← Previous: [10.1 Retry and Cache Policies](../10.1-retry-and-cache/README.md) · Next: [10.3 Error Handlers and Node Defaults](../10.3-error-handlers/README.md) →

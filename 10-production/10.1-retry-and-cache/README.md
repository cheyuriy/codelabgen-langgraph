# 10.1 Retry and Cache Policies

A node that fetches a shipping rate from a flaky simulated service retries with RetryPolicy, and an expensive address lookup is cached with CachePolicy and an in-memory cache, so repeated runs skip it.

## What you will learn

- Configure RetryPolicy on a node (max_attempts, backoff, retry_on) and observe the attempts
- Cache a node's result with CachePolicy and a cache backend, keyed by its input and with a ttl
- Explain which failures should be retried and which should not

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l10_1_retry_and_cache/__main__.py), [graph.py](src/l10_1_retry_and_cache/graph.py), [service.py](src/l10_1_retry_and_cache/service.py)

## How to run

From the course root:

```bash
./run.sh 10.1
```

Or by hand:

```bash
cd 10-production && uv sync --all-packages --quiet
cd 10.1-retry-and-cache
uv run --package l10-1-retry-and-cache python -m l10_1_retry_and_cache
```

Run the tests:

```bash
./run.sh test 10.1
```

← Previous: [9.2 Functional API: Memory, Interrupts and Determinism](../../9-functional-api/9.2-functional-memory-interrupts/README.md) · Next: [10.2 Node Timeouts](../10.2-node-timeouts/README.md) →

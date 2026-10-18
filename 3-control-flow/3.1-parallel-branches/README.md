# 3.1 Parallel Branches and Joins

Checks an order's stock, payment and address in parallel branches that join in a decision node. Shows fan-out and fan-in, why concurrent writes to one key need a reducer, and waiting edges with a list of sources.

## What you will learn

- Fan out to several nodes in one super-step and join them with add_edge([...], target)
- Explain the InvalidUpdateError raised when parallel nodes write the same key without a reducer
- Predict the order in which parallel results land in a reduced key

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l3_1_parallel_branches/__main__.py), [checks.py](src/l3_1_parallel_branches/checks.py)

## How to run

From the course root:

```bash
./run.sh 3.1
```

Or by hand:

```bash
cd 3-control-flow && uv sync --all-packages --quiet
cd 3.1-parallel-branches
uv run --package l3-1-parallel-branches python -m l3_1_parallel_branches
```

Run the tests:

```bash
./run.sh test 3.1
```

← Previous: [2.4 Runtime Context: Configuration Outside the State](../../2-state/2.4-runtime-context/README.md) · Next: [3.2 Map-Reduce with Send](../3.2-map-reduce-send/README.md) →

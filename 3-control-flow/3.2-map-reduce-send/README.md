# 3.2 Map-Reduce with Send

Prices every line item of the order in its own parallel task with Send, then sums the results. Shows dynamic fan-out from a conditional edge, per-task input, and max_concurrency.

> [!NOTE]
> This lesson continues the example from [3.1 Parallel Branches and Joins](../3.1-parallel-branches/README.md).

## What you will learn

- Fan out to a variable number of tasks by returning a list of Send objects from a conditional edge
- Give each task its own input that differs from the graph state and collect results with a reducer
- Limit parallel work with the max_concurrency run setting

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l3_2_map_reduce_send/__main__.py), [checks.py](src/l3_2_map_reduce_send/checks.py), [pricing.py](src/l3_2_map_reduce_send/pricing.py)

## How to run

From the course root:

```bash
./run.sh 3.2
```

Or by hand:

```bash
cd 3-control-flow && uv sync --all-packages --quiet
cd 3.2-map-reduce-send
uv run --package l3-2-map-reduce-send python -m l3_2_map_reduce_send
```

Run the tests:

```bash
./run.sh test 3.2
```

← Previous: [3.1 Parallel Branches and Joins](../3.1-parallel-branches/README.md) · Next: [3.3 Command: Update State and Route in One Step](../3.3-command/README.md) →

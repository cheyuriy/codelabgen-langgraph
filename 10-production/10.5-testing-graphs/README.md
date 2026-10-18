# 10.5 Testing Graphs with pytest

Tests the ticket router at three levels: individual nodes through the compiled graph's nodes mapping, the whole graph end to end, and a partial run that starts from a prepared state with update_state(as_node=...) and stops with interrupt_after.

## What you will learn

- Test a single node in isolation through compiled_graph.nodes
- Write end-to-end tests with a fresh checkpointer per test and fake models for LLM steps
- Run only part of a graph by seeding state with update_state(as_node=...) and stopping with interrupt_after

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__init__.py](src/l10_5_testing_graphs/__init__.py), [graph.py](src/l10_5_testing_graphs/graph.py)

## How to run

From the course root:

```bash
./run.sh 10.5
```

Or by hand:

```bash
cd 10-production && uv sync --all-packages --quiet
cd 10.5-testing-graphs
uv run --package l10-5-testing-graphs python -m pytest -v tests
```

Run the tests:

```bash
./run.sh test 10.5
```

← Previous: [10.4 Recovering a Failed Run](../10.4-recover-failed-run/README.md) · Next: [10.6 Application Structure and the Local Server](../10.6-local-server/README.md) →

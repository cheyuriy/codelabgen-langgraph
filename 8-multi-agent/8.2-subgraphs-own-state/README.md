# 8.2 Subgraphs with Their Own State

Adds a tech subgraph with a different state schema, called from inside a node that maps parent state in and the subgraph's output back. Shows reading subgraph state with get_state(subgraphs=True).

> [!NOTE]
> This lesson continues the example from [8.1 Subgraphs with Shared State](../8.1-subgraphs-shared-state/README.md).

## What you will learn

- Call a subgraph with a different schema from a node and transform state in both directions
- Read a subgraph's saved state through get_state(subgraphs=True)
- Choose between adding a subgraph as a node and invoking it inside a node

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l8_2_subgraphs_own_state/__main__.py), [billing.py](src/l8_2_subgraphs_own_state/billing.py), [desk.py](src/l8_2_subgraphs_own_state/desk.py), [show.py](src/l8_2_subgraphs_own_state/show.py), [tech.py](src/l8_2_subgraphs_own_state/tech.py)

## How to run

From the course root:

```bash
./run.sh 8.2
```

Or by hand:

```bash
cd 8-multi-agent && uv sync --all-packages --quiet
cd 8.2-subgraphs-own-state
uv run --package l8-2-subgraphs-own-state python -m l8_2_subgraphs_own_state
```

Run the tests:

```bash
./run.sh test 8.2
```

← Previous: [8.1 Subgraphs with Shared State](../8.1-subgraphs-shared-state/README.md) · Next: [8.3 Handoffs Between Agents with Command.PARENT](../8.3-agent-handoffs/README.md) →

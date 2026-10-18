# 3.3 Command: Update State and Route in One Step

Replaces the decision node's plain edge to END with a decide node that returns Command(update=..., goto=...) to approve, hold or cancel the order. Shows the return-type annotation that keeps the graph drawable and when Command beats an edge.

> [!NOTE]
> This lesson continues the example from [3.2 Map-Reduce with Send](../3.2-map-reduce-send/README.md).

## What you will learn

- Return Command with update and goto from a node to change state and choose the next node together
- Annotate Command[Literal[...]] so the graph knows the possible destinations
- Decide between a conditional edge and Command for a given routing need

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l3_3_command/__main__.py), [checks.py](src/l3_3_command/checks.py), [pricing.py](src/l3_3_command/pricing.py)

## How to run

From the course root:

```bash
./run.sh 3.3
```

Or by hand:

```bash
cd 3-control-flow && uv sync --all-packages --quiet
cd 3.3-command
uv run --package l3-3-command python -m l3_3_command
```

Run the tests:

```bash
./run.sh test 3.3
```

← Previous: [3.2 Map-Reduce with Send](../3.2-map-reduce-send/README.md) · Next: [4.1 Messages in State and an Offline Chat Model](../../4-agents/4.1-messages-state/README.md) →

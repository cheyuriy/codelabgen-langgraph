# 1.3 Loops, Super-steps and the Recursion Limit

Adds a draft-and-check loop: a reply is drafted, checked against simple rules and revised until it passes. Explains super-steps, the recursion_limit guard, GraphRecursionError, and RemainingSteps for stopping a loop gracefully.

> [!NOTE]
> This lesson continues the example from [1.2 Conditional Edges and Routing](../1.2-conditional-edges/README.md).

## What you will learn

- Build a cycle with a conditional edge that returns to an earlier node and ends on a condition
- Explain super-steps and how recursion_limit counts them, and handle GraphRecursionError
- Use the RemainingSteps managed value to leave a loop before the limit is hit

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l1_3_loops_and_recursion_limit/__main__.py), [graph.py](src/l1_3_loops_and_recursion_limit/graph.py)

## How to run

From the course root:

```bash
./run.sh 1.3
```

Or by hand:

```bash
cd 1-foundations && uv sync --all-packages --quiet
cd 1.3-loops-and-recursion-limit
uv run --package l1-3-loops-and-recursion-limit python -m l1_3_loops_and_recursion_limit
```

Run the tests:

```bash
./run.sh test 1.3
```

← Previous: [1.2 Conditional Edges and Routing](../1.2-conditional-edges/README.md) · Next: [2.1 State Schemas: TypedDict, Dataclass and Pydantic](../../2-state/2.1-state-schemas/README.md) →

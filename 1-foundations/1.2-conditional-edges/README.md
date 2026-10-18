# 1.2 Conditional Edges and Routing

Adds a classify step and a conditional edge that sends each ticket to a billing, tech or general queue node based on keywords. Shows routing functions, Literal return types and the path map, and what happens with an unknown route.

> [!NOTE]
> This lesson continues the example from [1.1 Your First Graph: State, Nodes and Edges](../1.1-hello-graph/README.md).

## What you will learn

- Route between nodes with add_conditional_edges and a routing function that reads the state
- Declare possible destinations with a Literal return type or a path map so the graph can be drawn and validated
- Explain when routing belongs in an edge rather than inside a node

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l1_2_conditional_edges/__main__.py), [graph.py](src/l1_2_conditional_edges/graph.py)

## How to run

From the course root:

```bash
./run.sh 1.2
```

Or by hand:

```bash
cd 1-foundations && uv sync --all-packages --quiet
cd 1.2-conditional-edges
uv run --package l1-2-conditional-edges python -m l1_2_conditional_edges
```

Run the tests:

```bash
./run.sh test 1.2
```

← Previous: [1.1 Your First Graph: State, Nodes and Edges](../1.1-hello-graph/README.md) · Next: [1.3 Loops, Super-steps and the Recursion Limit](../1.3-loops-and-recursion-limit/README.md) →

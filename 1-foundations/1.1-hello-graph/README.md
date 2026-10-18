# 1.1 Your First Graph: State, Nodes and Edges

Builds a linear StateGraph that cleans up a support ticket's text and tags its priority. Shows the TypedDict state, nodes as functions returning partial updates, START/END edges, compile() and invoke(), and printing the graph as Mermaid.

## What you will learn

- Describe graph state with a TypedDict and explain how a node's partial update is merged into it
- Wire nodes with add_node and add_edge between START and END, then compile and invoke the graph
- Print the compiled graph's structure with get_graph().draw_mermaid()

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l1_1_hello_graph/__main__.py), [graph.py](src/l1_1_hello_graph/graph.py)

## How to run

From the course root:

```bash
./run.sh 1.1
```

Or by hand:

```bash
cd 1-foundations && uv sync --all-packages --quiet
cd 1.1-hello-graph
uv run --package l1-1-hello-graph python -m l1_1_hello_graph
```

Run the tests:

```bash
./run.sh test 1.1
```

Next: [1.2 Conditional Edges and Routing](../1.2-conditional-edges/README.md) →

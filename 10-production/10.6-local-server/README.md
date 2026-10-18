# 10.6 Application Structure and the Local Server

Packages the support desk as an application: a graph factory module, langgraph.json, and langgraph dev serving it locally; a small script then creates a thread and runs the graph through the langgraph_sdk client.

## What you will learn

- Lay out a LangGraph application with a graph module, dependencies and langgraph.json
- Serve the graph locally with langgraph dev and explain what the server adds (threads, runs, persistence)
- Call the served graph from Python with the langgraph_sdk client

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l10_6_local_server/__main__.py), [billing.py](src/l10_6_local_server/billing.py), [client.py](src/l10_6_local_server/client.py), [desk.py](src/l10_6_local_server/desk.py), [graph.py](src/l10_6_local_server/graph.py), [server.py](src/l10_6_local_server/server.py)

## How to run

From the course root:

```bash
./run.sh 10.6
```

Or by hand:

```bash
cd 10-production && uv sync --all-packages --quiet
cd 10.6-local-server
uv run --package l10-6-local-server python -m l10_6_local_server
```

Run the tests:

```bash
./run.sh test 10.6
```

← Previous: [10.5 Testing Graphs with pytest](../10.5-testing-graphs/README.md)

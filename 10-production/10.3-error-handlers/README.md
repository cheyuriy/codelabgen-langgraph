# 10.3 Error Handlers and Node Defaults

When the rate lookup still fails, a node-level error_handler records the error and returns a fallback quote instead of crashing the run; set_node_defaults applies a retry policy, timeout and default handler to every node at once.

> [!NOTE]
> This lesson continues the example from [10.2 Node Timeouts](../10.2-node-timeouts/README.md).

## What you will learn

- Attach an error_handler to a node and turn a failure into a state update and a route
- Apply shared retry, timeout and error-handler settings with StateGraph.set_node_defaults
- Explain the order of retries, timeouts and error handlers, and the current limits with parallel nodes

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l10_3_error_handlers/__main__.py), [graph.py](src/l10_3_error_handlers/graph.py), [service.py](src/l10_3_error_handlers/service.py)

## How to run

From the course root:

```bash
./run.sh 10.3
```

Or by hand:

```bash
cd 10-production && uv sync --all-packages --quiet
cd 10.3-error-handlers
uv run --package l10-3-error-handlers python -m l10_3_error_handlers
```

Run the tests:

```bash
./run.sh test 10.3
```

← Previous: [10.2 Node Timeouts](../10.2-node-timeouts/README.md) · Next: [10.4 Recovering a Failed Run](../10.4-recover-failed-run/README.md) →

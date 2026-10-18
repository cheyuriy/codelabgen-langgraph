# 2.4 Runtime Context: Configuration Outside the State

Moves the tax rate and currency out of the state into a context_schema dataclass passed with invoke(context=...). Nodes read it through Runtime, so the same compiled graph serves different shops.

> [!NOTE]
> This lesson continues the example from [2.3 Input, Output and Private Schemas](../2.3-input-output-schemas/README.md).

## What you will learn

- Declare run-scoped settings with context_schema and pass them with context= at invoke time
- Read context inside a node through the runtime parameter typed as Runtime[Context]
- Explain the difference between state, context and config, and why config_schema is deprecated

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l2_4_runtime_context/__main__.py), [typed_dict_order.py](src/l2_4_runtime_context/typed_dict_order.py)

## How to run

From the course root:

```bash
./run.sh 2.4
```

Or by hand:

```bash
cd 2-state && uv sync --all-packages --quiet
cd 2.4-runtime-context
uv run --package l2-4-runtime-context python -m l2_4_runtime_context
```

Run the tests:

```bash
./run.sh test 2.4
```

← Previous: [2.3 Input, Output and Private Schemas](../2.3-input-output-schemas/README.md) · Next: [3.1 Parallel Branches and Joins](../../3-control-flow/3.1-parallel-branches/README.md) →

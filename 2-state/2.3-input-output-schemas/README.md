# 2.3 Input, Output and Private Schemas

Gives the order graph a narrow public interface: callers send only the cart, get back only the receipt, and intermediate values live in a private schema that nodes share.

> [!NOTE]
> This lesson continues the example from [2.2 Reducers: How Updates Are Combined](../2.2-reducers/README.md).

## What you will learn

- Constrain what a graph accepts and returns with input_schema and output_schema
- Pass internal values between nodes through a private schema that callers never see
- Explain how LangGraph builds the full set of channels from all schemas

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l2_3_input_output_schemas/__main__.py), [typed_dict_order.py](src/l2_3_input_output_schemas/typed_dict_order.py)

## How to run

From the course root:

```bash
./run.sh 2.3
```

Or by hand:

```bash
cd 2-state && uv sync --all-packages --quiet
cd 2.3-input-output-schemas
uv run --package l2-3-input-output-schemas python -m l2_3_input_output_schemas
```

Run the tests:

```bash
./run.sh test 2.3
```

← Previous: [2.2 Reducers: How Updates Are Combined](../2.2-reducers/README.md) · Next: [2.4 Runtime Context: Configuration Outside the State](../2.4-runtime-context/README.md) →

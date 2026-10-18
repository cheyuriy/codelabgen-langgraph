# 2.1 State Schemas: TypedDict, Dataclass and Pydantic

Models an online order as state in three styles and compares them: TypedDict for speed, a dataclass for defaults, Pydantic for validation of input. Shows what validation does and does not cover, and how version="v2" coerces the output.

## What you will learn

- Choose between TypedDict, dataclass and Pydantic state schemas and explain the trade-offs
- Show that a Pydantic schema validates graph input and rejects bad data
- Get typed output from invoke(..., version="v2") through GraphOutput.value

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l2_1_state_schemas/__main__.py), [dataclass_order.py](src/l2_1_state_schemas/dataclass_order.py), [pydantic_order.py](src/l2_1_state_schemas/pydantic_order.py), [typed_dict_order.py](src/l2_1_state_schemas/typed_dict_order.py)

## How to run

From the course root:

```bash
./run.sh 2.1
```

Or by hand:

```bash
cd 2-state && uv sync --all-packages --quiet
cd 2.1-state-schemas
uv run --package l2-1-state-schemas python -m l2_1_state_schemas
```

Run the tests:

```bash
./run.sh test 2.1
```

← Previous: [1.3 Loops, Super-steps and the Recursion Limit](../../1-foundations/1.3-loops-and-recursion-limit/README.md) · Next: [2.2 Reducers: How Updates Are Combined](../2.2-reducers/README.md) →

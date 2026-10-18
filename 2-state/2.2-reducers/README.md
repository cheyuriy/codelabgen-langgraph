# 2.2 Reducers: How Updates Are Combined

Adds line items and an audit log to the order. Default overwrite versus Annotated reducers (operator.add and a custom merge function), and Overwrite to replace a reduced value on purpose.

> [!NOTE]
> This lesson continues the example from [2.1 State Schemas: TypedDict, Dataclass and Pydantic](../2.1-state-schemas/README.md).

## What you will learn

- Explain the default overwrite behaviour and attach a reducer to a key with Annotated
- Write a custom reducer function and predict the state it produces
- Bypass a reducer with Overwrite to reset an accumulated value

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l2_2_reducers/__main__.py), [typed_dict_order.py](src/l2_2_reducers/typed_dict_order.py)

## How to run

From the course root:

```bash
./run.sh 2.2
```

Or by hand:

```bash
cd 2-state && uv sync --all-packages --quiet
cd 2.2-reducers
uv run --package l2-2-reducers python -m l2_2_reducers
```

Run the tests:

```bash
./run.sh test 2.2
```

← Previous: [2.1 State Schemas: TypedDict, Dataclass and Pydantic](../2.1-state-schemas/README.md) · Next: [2.3 Input, Output and Private Schemas](../2.3-input-output-schemas/README.md) →

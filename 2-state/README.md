# 2 State in Depth

How state is declared, merged and exposed: schema types, reducers, separate input, output and private schemas, and run-scoped context that is not part of the state.

## Lessons

- [2.1 State Schemas: TypedDict, Dataclass and Pydantic](2.1-state-schemas/README.md) — Models an online order as state in three styles and compares them: TypedDict for speed, a dataclass for defaults, Pydantic for validation of input. Shows what validation does and does not cover, and how version="v2" coerces the output.
- [2.2 Reducers: How Updates Are Combined](2.2-reducers/README.md) — Adds line items and an audit log to the order. Default overwrite versus Annotated reducers (operator.add and a custom merge function), and Overwrite to replace a reduced value on purpose.
- [2.3 Input, Output and Private Schemas](2.3-input-output-schemas/README.md) — Gives the order graph a narrow public interface: callers send only the cart, get back only the receipt, and intermediate values live in a private schema that nodes share.
- [2.4 Runtime Context: Configuration Outside the State](2.4-runtime-context/README.md) — Moves the tax rate and currency out of the state into a context_schema dataclass passed with invoke(context=...). Nodes read it through Runtime, so the same compiled graph serves different shops.

[Home](../README.md)

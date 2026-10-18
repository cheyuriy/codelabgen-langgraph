# 9 The Functional API

The same runtime without an explicit graph: @entrypoint and @task over ordinary Python control flow, with checkpointing, short-term memory and interrupts.

## Lessons

- [9.1 @entrypoint and @task](9.1-entrypoint-and-task/README.md) — Rewrites an order-processing workflow as an @entrypoint function that calls @task functions, runs two of them concurrently through futures, and is checkpointed per task. Compares the code with the equivalent StateGraph.
- [9.2 Functional API: Memory, Interrupts and Determinism](9.2-functional-memory-interrupts/README.md) — Adds an approval interrupt and a running order count. On resume the entrypoint replays from the start but finished tasks return their saved results; shows previous, entrypoint.final, and why side effects belong in tasks.

[Home](../README.md)

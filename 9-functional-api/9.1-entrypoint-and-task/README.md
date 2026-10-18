# 9.1 @entrypoint and @task

Rewrites an order-processing workflow as an @entrypoint function that calls @task functions, runs two of them concurrently through futures, and is checkpointed per task. Compares the code with the equivalent StateGraph.

## What you will learn

- Define a workflow with @entrypoint and units of work with @task, and run tasks concurrently via .result()
- Attach a checkpointer to an entrypoint and invoke it with a thread_id
- Compare the Functional API with the Graph API and choose between them

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__init__.py](src/l9_1_entrypoint_and_task/__init__.py), [__main__.py](src/l9_1_entrypoint_and_task/__main__.py), [workflow.py](src/l9_1_entrypoint_and_task/workflow.py)

## How to run

From the course root:

```bash
./run.sh 9.1
```

Or by hand:

```bash
cd 9-functional-api && uv sync --all-packages --quiet
cd 9.1-entrypoint-and-task
uv run --package l9-1-entrypoint-and-task python -m l9_1_entrypoint_and_task
```

Run the tests:

```bash
./run.sh test 9.1
```

← Previous: [8.4 A Supervisor with Specialist Agents as Tools](../../8-multi-agent/8.4-supervisor-agents/README.md) · Next: [9.2 Functional API: Memory, Interrupts and Determinism](../9.2-functional-memory-interrupts/README.md) →

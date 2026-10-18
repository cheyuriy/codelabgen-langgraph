# 8.4 A Supervisor with Specialist Agents as Tools

A supervisor agent answers customer questions by calling a billing agent and a shipping agent wrapped as tools, each built with create_agent and driven by scripted fake models. Contrasts the supervisor pattern with handoffs.

## What you will learn

- Wrap a compiled agent as a tool and let a supervisor agent call it
- Trace how one user request flows through supervisor and specialist runs
- Compare supervisor (agents as tools) and handoff architectures

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l8_4_supervisor_agents/__main__.py), [fake_model.py](src/l8_4_supervisor_agents/fake_model.py), [scripts.py](src/l8_4_supervisor_agents/scripts.py), [show.py](src/l8_4_supervisor_agents/show.py), [specialists.py](src/l8_4_supervisor_agents/specialists.py), [supervisor.py](src/l8_4_supervisor_agents/supervisor.py)

## How to run

From the course root:

```bash
./run.sh 8.4
```

Or by hand:

```bash
cd 8-multi-agent && uv sync --all-packages --quiet
cd 8.4-supervisor-agents
uv run --package l8-4-supervisor-agents python -m l8_4_supervisor_agents
```

Run the tests:

```bash
./run.sh test 8.4
```

← Previous: [8.3 Handoffs Between Agents with Command.PARENT](../8.3-agent-handoffs/README.md) · Next: [9.1 @entrypoint and @task](../../9-functional-api/9.1-entrypoint-and-task/README.md) →

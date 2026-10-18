# 8.3 Handoffs Between Agents with Command.PARENT

The billing and tech subgraphs become agents that can hand a ticket to each other: a node inside one subgraph returns Command(goto=..., graph=Command.PARENT) to jump to a sibling in the parent graph and pass along an update.

> [!NOTE]
> This lesson continues the example from [8.2 Subgraphs with Their Own State](../8.2-subgraphs-own-state/README.md).

## What you will learn

- Hand control from inside a subgraph to a node of the parent graph with Command.PARENT
- Pass state with a handoff and declare a reducer for keys updated across graph levels
- Describe the handoff (swarm-style) multi-agent pattern and its trade-offs

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l8_3_agent_handoffs/__main__.py), [billing.py](src/l8_3_agent_handoffs/billing.py), [desk.py](src/l8_3_agent_handoffs/desk.py), [handoff.py](src/l8_3_agent_handoffs/handoff.py), [show.py](src/l8_3_agent_handoffs/show.py), [tech.py](src/l8_3_agent_handoffs/tech.py)

## How to run

From the course root:

```bash
./run.sh 8.3
```

Or by hand:

```bash
cd 8-multi-agent && uv sync --all-packages --quiet
cd 8.3-agent-handoffs
uv run --package l8-3-agent-handoffs python -m l8_3_agent_handoffs
```

Run the tests:

```bash
./run.sh test 8.3
```

← Previous: [8.2 Subgraphs with Their Own State](../8.2-subgraphs-own-state/README.md) · Next: [8.4 A Supervisor with Specialist Agents as Tools](../8.4-supervisor-agents/README.md) →

# 6.4 Approving Tool Calls Inside an Agent

A to-do agent may add tasks freely but must ask before deleting one: the delete tool calls interrupt() itself, so the agent loop pauses inside ToolNode and the human's answer becomes the tool result.

## What you will learn

- Call interrupt() inside a tool to gate a risky action behind human approval
- Resume the agent so the approval or rejection is returned as the ToolMessage content
- Explain how a tool interrupt interacts with the agent loop and the checkpoint

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l6_4_interrupts_in_tools/__main__.py), [agent.py](src/l6_4_interrupts_in_tools/agent.py), [todos.py](src/l6_4_interrupts_in_tools/todos.py)

## How to run

From the course root:

```bash
./run.sh 6.4
```

Or by hand:

```bash
cd 6-human-in-the-loop && uv sync --all-packages --quiet
cd 6.4-interrupts-in-tools
uv run --package l6-4-interrupts-in-tools python -m l6_4_interrupts_in_tools
```

Run the tests:

```bash
./run.sh test 6.4
```

← Previous: [6.3 The Rules of Interrupts](../6.3-rules-of-interrupts/README.md) · Next: [6.5 Time Travel: History, Replay and Forks](../6.5-time-travel/README.md) →

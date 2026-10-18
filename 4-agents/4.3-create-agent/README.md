# 4.3 The Prebuilt Agent with create_agent

Rebuilds the calculator agent with langchain's create_agent and compares it to the hand-built graph: same loop, same tools, a system prompt, and a compiled LangGraph graph underneath. Notes the migration from the deprecated create_react_agent.

> [!NOTE]
> This lesson continues the example from [4.2 A Tool-Calling Agent Loop by Hand](../4.2-tool-calling-loop/README.md).

## What you will learn

- Build an agent with create_agent from a model, tools and a system_prompt
- Show that the result is a compiled LangGraph graph that can be invoked, streamed and inspected
- Decide when the prebuilt agent is enough and when to write the graph yourself

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l4_3_create_agent/__main__.py), [agent.py](src/l4_3_create_agent/agent.py), [chatbot.py](src/l4_3_create_agent/chatbot.py), [tools.py](src/l4_3_create_agent/tools.py)

## How to run

From the course root:

```bash
./run.sh 4.3
```

Or by hand:

```bash
cd 4-agents && uv sync --all-packages --quiet
cd 4.3-create-agent
uv run --package l4-3-create-agent python -m l4_3_create_agent
```

Run the tests:

```bash
./run.sh test 4.3
```

← Previous: [4.2 A Tool-Calling Agent Loop by Hand](../4.2-tool-calling-loop/README.md) · Next: [5.1 Checkpointers and Threads](../../5-persistence/5.1-checkpointers-and-threads/README.md) →

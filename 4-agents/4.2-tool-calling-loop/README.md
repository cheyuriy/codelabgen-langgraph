# 4.2 A Tool-Calling Agent Loop by Hand

Turns the chatbot into the official quickstart's calculator agent: add, multiply and divide tools, a model node whose scripted replies contain tool calls, ToolNode, tools_condition and the edge back to the model. The ReAct loop, built explicitly.

> [!NOTE]
> This lesson continues the example from [4.1 Messages in State and an Offline Chat Model](../4.1-messages-state/README.md).

## What you will learn

- Define tools with @tool and run requested calls with ToolNode
- Close the agent loop with tools_condition and an edge from the tools back to the model
- Explain the pairing rule between an AIMessage tool call and its ToolMessage

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l4_2_tool_calling_loop/__main__.py), [chatbot.py](src/l4_2_tool_calling_loop/chatbot.py), [tools.py](src/l4_2_tool_calling_loop/tools.py)

## How to run

From the course root:

```bash
./run.sh 4.2
```

Or by hand:

```bash
cd 4-agents && uv sync --all-packages --quiet
cd 4.2-tool-calling-loop
uv run --package l4-2-tool-calling-loop python -m l4_2_tool_calling_loop
```

Run the tests:

```bash
./run.sh test 4.2
```

← Previous: [4.1 Messages in State and an Offline Chat Model](../4.1-messages-state/README.md) · Next: [4.3 The Prebuilt Agent with create_agent](../4.3-create-agent/README.md) →

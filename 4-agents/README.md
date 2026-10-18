# 4 Agents: Messages and Tools

The classic agent loop: chat messages in state, a model node that requests tool calls, a tool node that runs them, and the prebuilt create_agent that packages the same loop.

## Lessons

- [4.1 Messages in State and an Offline Chat Model](4.1-messages-state/README.md) — Builds a one-node chatbot on MessagesState with a scripted fake chat model so it runs offline. Explains add_messages: appending, merging by message id, and deleting with RemoveMessage, compared with plain list concatenation.
- [4.2 A Tool-Calling Agent Loop by Hand](4.2-tool-calling-loop/README.md) — Turns the chatbot into the official quickstart's calculator agent: add, multiply and divide tools, a model node whose scripted replies contain tool calls, ToolNode, tools_condition and the edge back to the model. The ReAct loop, built explicitly.
- [4.3 The Prebuilt Agent with create_agent](4.3-create-agent/README.md) — Rebuilds the calculator agent with langchain's create_agent and compares it to the hand-built graph: same loop, same tools, a system prompt, and a compiled LangGraph graph underneath. Notes the migration from the deprecated create_react_agent.

[Home](../README.md)

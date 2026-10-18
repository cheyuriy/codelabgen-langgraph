# 8 Subgraphs and Multi-Agent Systems

Composing graphs from graphs: subgraphs with shared or separate state, their persistence and streams, handoffs between agents with Command.PARENT, and a supervisor that calls specialist agents as tools.

## Lessons

- [8.1 Subgraphs with Shared State](8.1-subgraphs-shared-state/README.md) — A support desk graph adds a compiled billing subgraph directly as a node; parent and subgraph communicate through shared keys. Shows get_graph(xray=True) and streaming with subgraphs=True to see namespaced updates.
- [8.2 Subgraphs with Their Own State](8.2-subgraphs-own-state/README.md) — Adds a tech subgraph with a different state schema, called from inside a node that maps parent state in and the subgraph's output back. Shows reading subgraph state with get_state(subgraphs=True).
- [8.3 Handoffs Between Agents with Command.PARENT](8.3-agent-handoffs/README.md) — The billing and tech subgraphs become agents that can hand a ticket to each other: a node inside one subgraph returns Command(goto=..., graph=Command.PARENT) to jump to a sibling in the parent graph and pass along an update.
- [8.4 A Supervisor with Specialist Agents as Tools](8.4-supervisor-agents/README.md) — A supervisor agent answers customer questions by calling a billing agent and a shipping agent wrapped as tools, each built with create_agent and driven by scripted fake models. Contrasts the supervisor pattern with handoffs.

[Home](../README.md)

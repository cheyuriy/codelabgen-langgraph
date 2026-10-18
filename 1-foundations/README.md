# 1 Graph Foundations

What a LangGraph program is: a typed state, nodes that return partial updates, and edges that decide what runs next, including conditional routing and loops.

## Lessons

- [1.1 Your First Graph: State, Nodes and Edges](1.1-hello-graph/README.md) — Builds a linear StateGraph that cleans up a support ticket's text and tags its priority. Shows the TypedDict state, nodes as functions returning partial updates, START/END edges, compile() and invoke(), and printing the graph as Mermaid.
- [1.2 Conditional Edges and Routing](1.2-conditional-edges/README.md) — Adds a classify step and a conditional edge that sends each ticket to a billing, tech or general queue node based on keywords. Shows routing functions, Literal return types and the path map, and what happens with an unknown route.
- [1.3 Loops, Super-steps and the Recursion Limit](1.3-loops-and-recursion-limit/README.md) — Adds a draft-and-check loop: a reply is drafted, checked against simple rules and revised until it passes. Explains super-steps, the recursion_limit guard, GraphRecursionError, and RemainingSteps for stopping a loop gracefully.

[Home](../README.md)

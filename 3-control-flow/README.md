# 3 Control Flow: Parallelism, Send and Command

Running nodes in parallel, fanning out over a dynamic number of items, and letting a node update state and choose the next step in one return value.

## Lessons

- [3.1 Parallel Branches and Joins](3.1-parallel-branches/README.md) — Checks an order's stock, payment and address in parallel branches that join in a decision node. Shows fan-out and fan-in, why concurrent writes to one key need a reducer, and waiting edges with a list of sources.
- [3.2 Map-Reduce with Send](3.2-map-reduce-send/README.md) — Prices every line item of the order in its own parallel task with Send, then sums the results. Shows dynamic fan-out from a conditional edge, per-task input, and max_concurrency.
- [3.3 Command: Update State and Route in One Step](3.3-command/README.md) — Replaces the decision node's plain edge to END with a decide node that returns Command(update=..., goto=...) to approve, hold or cancel the order. Shows the return-type annotation that keeps the graph drawable and when Command beats an edge.

[Home](../README.md)

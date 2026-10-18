# 10 Reliability, Testing and Deployment

Making graphs dependable: retries, caching, node timeouts, error handlers and node defaults, recovering a failed run, testing graphs with pytest, and packaging an application for the local LangGraph server.

## Lessons

- [10.1 Retry and Cache Policies](10.1-retry-and-cache/README.md) — A node that fetches a shipping rate from a flaky simulated service retries with RetryPolicy, and an expensive address lookup is cached with CachePolicy and an in-memory cache, so repeated runs skip it.
- [10.2 Node Timeouts](10.2-node-timeouts/README.md) — Puts a timeout on the slow rate lookup: a hard timeout raises NodeTimeoutError, a TimeoutPolicy with an idle timeout lets a long node stay alive by calling runtime.heartbeat(), and timeouts combine with retries.
- [10.3 Error Handlers and Node Defaults](10.3-error-handlers/README.md) — When the rate lookup still fails, a node-level error_handler records the error and returns a fallback quote instead of crashing the run; set_node_defaults applies a retry policy, timeout and default handler to every node at once.
- [10.4 Recovering a Failed Run](10.4-recover-failed-run/README.md) — A run fails mid-way after some nodes have finished. With a checkpointer the finished work is kept (including pending writes of parallel siblings), the cause is fixed, and the run resumes with invoke(None) on the same thread.
- [10.5 Testing Graphs with pytest](10.5-testing-graphs/README.md) — Tests the ticket router at three levels: individual nodes through the compiled graph's nodes mapping, the whole graph end to end, and a partial run that starts from a prepared state with update_state(as_node=...) and stops with interrupt_after.
- [10.6 Application Structure and the Local Server](10.6-local-server/README.md) — Packages the support desk as an application: a graph factory module, langgraph.json, and langgraph dev serving it locally; a small script then creates a thread and runs the graph through the langgraph_sdk client.

[Home](../README.md)

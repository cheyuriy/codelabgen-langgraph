# LangGraph 1.2 in Practice: From a First Graph to Reliable Agents

Learn LangGraph by running it. This course takes you from your first graph to agents that you can pause, resume, stream and test, with one small working program per lesson.

- **No API keys, no surprises.** LLM steps use scripted fake chat models, so every example runs offline and gives the same result on your machine.
- **Learn by changing code.** Each lesson is a short program with tests, a walkthrough of its code, notes on the concept and experiments to try.
- **Examples that grow.** A support-ticket router, an online order, a calculator agent and a reading-list assistant build up from lesson to lesson.
- **Current APIs only.** Written for LangGraph 1.2.16: `interrupt()` and `Command`, `InMemorySaver`, `create_agent`, typed v2 streaming.

**What you will learn:** state and routing, tool-calling agents, persistence and memory, human-in-the-loop, streaming, subgraphs and multi-agent handoffs, the Functional API, and production patterns such as retries, timeouts, caching, error handling and testing.

**Who it is for:** Python developers who are comfortable with type hints (`TypedDict`, `Annotated`) and know the basics of chat messages and LLM tool calls. No LangGraph experience needed.

**Not covered:** the JS/TS version, LangSmith, hosted deployment on Agent Server, and LangGraph internals.

## Getting started

1. You need [uv](https://docs.astral.sh/uv/) and [Docker](https://docs.docker.com/engine/install/).
2. Copy `.env.example` to `.env` and fill in the values.
3. Run a lesson from the course root:

   ```bash
   ./run.sh 1.1
   ```

4. Browse the course as a website:

   ```bash
   ./run.sh site serve
   ```

5. Try your own experiments in a separate git branch, so the original lessons stay as they are and you can always compare with them or start again:

   ```bash
   git switch -c my-experiments
   ```

## Contents

### [1 Graph Foundations](1-foundations/README.md)

What a LangGraph program is: a typed state, nodes that return partial updates, and edges that decide what runs next, including conditional routing and loops.

- [1.1 Your First Graph: State, Nodes and Edges](1-foundations/1.1-hello-graph/README.md) — Builds a linear StateGraph that cleans up a support ticket's text and tags its priority. Shows the TypedDict state, nodes as functions returning partial updates, START/END edges, compile() and invoke(), and printing the graph as Mermaid.
- [1.2 Conditional Edges and Routing](1-foundations/1.2-conditional-edges/README.md) — Adds a classify step and a conditional edge that sends each ticket to a billing, tech or general queue node based on keywords. Shows routing functions, Literal return types and the path map, and what happens with an unknown route.
- [1.3 Loops, Super-steps and the Recursion Limit](1-foundations/1.3-loops-and-recursion-limit/README.md) — Adds a draft-and-check loop: a reply is drafted, checked against simple rules and revised until it passes. Explains super-steps, the recursion_limit guard, GraphRecursionError, and RemainingSteps for stopping a loop gracefully.

### [2 State in Depth](2-state/README.md)

How state is declared, merged and exposed: schema types, reducers, separate input, output and private schemas, and run-scoped context that is not part of the state.

- [2.1 State Schemas: TypedDict, Dataclass and Pydantic](2-state/2.1-state-schemas/README.md) — Models an online order as state in three styles and compares them: TypedDict for speed, a dataclass for defaults, Pydantic for validation of input. Shows what validation does and does not cover, and how version="v2" coerces the output.
- [2.2 Reducers: How Updates Are Combined](2-state/2.2-reducers/README.md) — Adds line items and an audit log to the order. Default overwrite versus Annotated reducers (operator.add and a custom merge function), and Overwrite to replace a reduced value on purpose.
- [2.3 Input, Output and Private Schemas](2-state/2.3-input-output-schemas/README.md) — Gives the order graph a narrow public interface: callers send only the cart, get back only the receipt, and intermediate values live in a private schema that nodes share.
- [2.4 Runtime Context: Configuration Outside the State](2-state/2.4-runtime-context/README.md) — Moves the tax rate and currency out of the state into a context_schema dataclass passed with invoke(context=...). Nodes read it through Runtime, so the same compiled graph serves different shops.

### [3 Control Flow: Parallelism, Send and Command](3-control-flow/README.md)

Running nodes in parallel, fanning out over a dynamic number of items, and letting a node update state and choose the next step in one return value.

- [3.1 Parallel Branches and Joins](3-control-flow/3.1-parallel-branches/README.md) — Checks an order's stock, payment and address in parallel branches that join in a decision node. Shows fan-out and fan-in, why concurrent writes to one key need a reducer, and waiting edges with a list of sources.
- [3.2 Map-Reduce with Send](3-control-flow/3.2-map-reduce-send/README.md) — Prices every line item of the order in its own parallel task with Send, then sums the results. Shows dynamic fan-out from a conditional edge, per-task input, and max_concurrency.
- [3.3 Command: Update State and Route in One Step](3-control-flow/3.3-command/README.md) — Replaces the decision node's plain edge to END with a decide node that returns Command(update=..., goto=...) to approve, hold or cancel the order. Shows the return-type annotation that keeps the graph drawable and when Command beats an edge.

### [4 Agents: Messages and Tools](4-agents/README.md)

The classic agent loop: chat messages in state, a model node that requests tool calls, a tool node that runs them, and the prebuilt create_agent that packages the same loop.

- [4.1 Messages in State and an Offline Chat Model](4-agents/4.1-messages-state/README.md) — Builds a one-node chatbot on MessagesState with a scripted fake chat model so it runs offline. Explains add_messages: appending, merging by message id, and deleting with RemoveMessage, compared with plain list concatenation.
- [4.2 A Tool-Calling Agent Loop by Hand](4-agents/4.2-tool-calling-loop/README.md) — Turns the chatbot into the official quickstart's calculator agent: add, multiply and divide tools, a model node whose scripted replies contain tool calls, ToolNode, tools_condition and the edge back to the model. The ReAct loop, built explicitly.
- [4.3 The Prebuilt Agent with create_agent](4-agents/4.3-create-agent/README.md) — Rebuilds the calculator agent with langchain's create_agent and compares it to the hand-built graph: same loop, same tools, a system prompt, and a compiled LangGraph graph underneath. Notes the migration from the deprecated create_react_agent.

### [5 Persistence and Memory](5-persistence/README.md)

Saving state at every super-step with checkpointers: conversations per thread, durable storage in SQLite and Postgres, managing a growing history, and stores for memory that is shared across threads.

- [5.1 Checkpointers and Threads](5-persistence/5.1-checkpointers-and-threads/README.md) — Starts from a compact copy of the calculator agent and adds InMemorySaver, so it remembers earlier turns within a thread_id and starts fresh in another. Shows get_state and the StateSnapshot it returns.
- [5.2 Durable Checkpoints with SQLite](5-persistence/5.2-sqlite-checkpointer/README.md) — Swaps InMemorySaver for SqliteSaver so a conversation survives a process restart: the run is executed twice as separate processes on the same database file. Covers from_conn_string and the durability modes (exit, async, sync).
- [5.3 Trimming and Summarizing Message History](5-persistence/5.3-message-history/README.md) — Keeps a long conversation small: trims what is sent to the model with trim_messages, deletes old messages from state with RemoveMessage, and folds them into a running summary kept in the state.
- [5.4 Long-Term Memory with a Store](5-persistence/5.4-long-term-memory-store/README.md) — A reading-list assistant remembers a user's favourite genres across threads with InMemoryStore: namespaces per user, put, get and search, and runtime.store inside nodes, next to the per-thread checkpointer.
- [5.5 Semantic Search over Memories](5-persistence/5.5-semantic-memory-search/README.md) — Gives the store an embedding index so the assistant finds memories by meaning rather than by key. Uses a deterministic fake embedding so search results are reproducible offline.
- [5.6 Postgres Checkpointer and Store for Production](5-persistence/5.6-postgres-persistence/README.md) — Runs the reading-list assistant on PostgresSaver and PostgresStore against a real Postgres server: connection strings from the environment, setup(), and sharing state between two separate processes.

### [6 Human-in-the-Loop and Time Travel](6-human-in-the-loop/README.md)

Pausing a run for a person with interrupt(), resuming it with Command(resume=...), the common approval and editing patterns, the rules that keep resumes correct, and going back in a thread's history.

- [6.1 Pausing with interrupt() and Resuming with Command](6-human-in-the-loop/6.1-interrupt-and-resume/README.md) — A refund request above a limit pauses for a manager's decision. Shows interrupt() with a payload, why a checkpointer and thread_id are required, reading the pending interrupt (v1 __interrupt__ and v2 GraphOutput.interrupts), and resuming with Command(resume=...).
- [6.2 Approve, Edit and Validate: Interrupt Patterns](6-human-in-the-loop/6.2-interrupt-patterns/README.md) — Extends the refund flow with the three standard patterns: approve or reject with Command routing, let the manager edit the refund amount before it is applied, and re-ask in a loop until the human input is valid.
- [6.3 The Rules of Interrupts](6-human-in-the-loop/6.3-rules-of-interrupts/README.md) — Shows, with counters in the refund flow, that a resumed node re-runs from its start: side effects before interrupt() run twice unless made idempotent, several interrupts in one node are matched by order, and parallel interrupts are resumed with a map keyed by Interrupt.id.
- [6.4 Approving Tool Calls Inside an Agent](6-human-in-the-loop/6.4-interrupts-in-tools/README.md) — A to-do agent may add tasks freely but must ask before deleting one: the delete tool calls interrupt() itself, so the agent loop pauses inside ToolNode and the human's answer becomes the tool result.
- [6.5 Time Travel: History, Replay and Forks](6-human-in-the-loop/6.5-time-travel/README.md) — Walks back through the refund thread with get_state_history, replays from an earlier checkpoint, and forks it with update_state (including as_node) to try a different decision, comparing replay with fork.

### [7 Streaming](7-streaming/README.md)

Showing progress while a graph runs: state and update streams, typed v2 stream parts, custom progress events, LLM tokens, and the newer event streaming API.

- [7.1 Stream Modes: values, updates and Typed v2 Parts](7-streaming/7.1-stream-modes/README.md) — Streams an order-fulfilment graph (pick, pack, ship) with stream_mode values and updates, then several modes at once, and switches to version="v2" so every chunk is a typed StreamPart with type, ns and data.
- [7.2 Custom Progress Events with get_stream_writer](7-streaming/7.2-custom-stream-data/README.md) — The packing node reports per-item progress with get_stream_writer, and the caller prints it from stream_mode="custom" next to the regular updates.
- [7.3 Streaming LLM Tokens](7-streaming/7.3-streaming-llm-tokens/README.md) — Adds a node that writes a shipping confirmation with a fake chat model that streams chunk by chunk. Uses stream_mode="messages", filters tokens by node via metadata and by tags, and keeps a model silent with nostream.
- [7.4 Event Streaming with stream_events v3](7-streaming/7.4-event-streaming/README.md) — Consumes the same run through stream_events(version="v3"): a run stream object with typed projections for values, messages and the final output, compared with the stream-mode API.

### [8 Subgraphs and Multi-Agent Systems](8-multi-agent/README.md)

Composing graphs from graphs: subgraphs with shared or separate state, their persistence and streams, handoffs between agents with Command.PARENT, and a supervisor that calls specialist agents as tools.

- [8.1 Subgraphs with Shared State](8-multi-agent/8.1-subgraphs-shared-state/README.md) — A support desk graph adds a compiled billing subgraph directly as a node; parent and subgraph communicate through shared keys. Shows get_graph(xray=True) and streaming with subgraphs=True to see namespaced updates.
- [8.2 Subgraphs with Their Own State](8-multi-agent/8.2-subgraphs-own-state/README.md) — Adds a tech subgraph with a different state schema, called from inside a node that maps parent state in and the subgraph's output back. Shows reading subgraph state with get_state(subgraphs=True).
- [8.3 Handoffs Between Agents with Command.PARENT](8-multi-agent/8.3-agent-handoffs/README.md) — The billing and tech subgraphs become agents that can hand a ticket to each other: a node inside one subgraph returns Command(goto=..., graph=Command.PARENT) to jump to a sibling in the parent graph and pass along an update.
- [8.4 A Supervisor with Specialist Agents as Tools](8-multi-agent/8.4-supervisor-agents/README.md) — A supervisor agent answers customer questions by calling a billing agent and a shipping agent wrapped as tools, each built with create_agent and driven by scripted fake models. Contrasts the supervisor pattern with handoffs.

### [9 The Functional API](9-functional-api/README.md)

The same runtime without an explicit graph: @entrypoint and @task over ordinary Python control flow, with checkpointing, short-term memory and interrupts.

- [9.1 @entrypoint and @task](9-functional-api/9.1-entrypoint-and-task/README.md) — Rewrites an order-processing workflow as an @entrypoint function that calls @task functions, runs two of them concurrently through futures, and is checkpointed per task. Compares the code with the equivalent StateGraph.
- [9.2 Functional API: Memory, Interrupts and Determinism](9-functional-api/9.2-functional-memory-interrupts/README.md) — Adds an approval interrupt and a running order count. On resume the entrypoint replays from the start but finished tasks return their saved results; shows previous, entrypoint.final, and why side effects belong in tasks.

### [10 Reliability, Testing and Deployment](10-production/README.md)

Making graphs dependable: retries, caching, node timeouts, error handlers and node defaults, recovering a failed run, testing graphs with pytest, and packaging an application for the local LangGraph server.

- [10.1 Retry and Cache Policies](10-production/10.1-retry-and-cache/README.md) — A node that fetches a shipping rate from a flaky simulated service retries with RetryPolicy, and an expensive address lookup is cached with CachePolicy and an in-memory cache, so repeated runs skip it.
- [10.2 Node Timeouts](10-production/10.2-node-timeouts/README.md) — Puts a timeout on the slow rate lookup: a hard timeout raises NodeTimeoutError, a TimeoutPolicy with an idle timeout lets a long node stay alive by calling runtime.heartbeat(), and timeouts combine with retries.
- [10.3 Error Handlers and Node Defaults](10-production/10.3-error-handlers/README.md) — When the rate lookup still fails, a node-level error_handler records the error and returns a fallback quote instead of crashing the run; set_node_defaults applies a retry policy, timeout and default handler to every node at once.
- [10.4 Recovering a Failed Run](10-production/10.4-recover-failed-run/README.md) — A run fails mid-way after some nodes have finished. With a checkpointer the finished work is kept (including pending writes of parallel siblings), the cause is fixed, and the run resumes with invoke(None) on the same thread.
- [10.5 Testing Graphs with pytest](10-production/10.5-testing-graphs/README.md) — Tests the ticket router at three levels: individual nodes through the compiled graph's nodes mapping, the whole graph end to end, and a partial run that starts from a prepared state with update_state(as_node=...) and stops with interrupt_after.
- [10.6 Application Structure and the Local Server](10-production/10.6-local-server/README.md) — Packages the support desk as an application: a graph factory module, langgraph.json, and langgraph dev serving it locally; a small script then creates a thread and runs the graph through the langgraph_sdk client.

[Glossary](GLOSSARY.md)

## Sources

The course is built on these materials.

### Official documentation

- [Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph Python API reference](https://reference.langchain.com/python/langgraph)
- [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- [Functional API overview](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)

### Release notes

- [langgraph 1.1.0 release notes](https://github.com/langchain-ai/langgraph/releases/tag/1.1.0)
- [langgraph 1.2.0 release notes](https://github.com/langchain-ai/langgraph/releases/tag/1.2.0)

### Official blog

- [Building LangGraph: Designing an Agent Runtime from first principles](https://langchain.com/blog/building-langgraph)

### Package source and tests

- [langgraph core tests (1.2.16)](https://github.com/langchain-ai/langgraph/tree/1.2.16/libs/langgraph/tests)
- [LangChain docs llms.txt](https://docs.langchain.com/llms.txt)
- [langgraph package source (graph, pregel, channels, func, types)](https://github.com/langchain-ai/langgraph/tree/1.2.16/libs/langgraph/langgraph)
- [langgraph examples (notebooks and apps)](https://github.com/langchain-ai/langgraph/tree/1.2.16/examples)

### GitHub repositories

- [LangChain Academy: Introduction to LangGraph](https://github.com/langchain-ai/langchain-academy)
- [langchain-ai/react-agent](https://github.com/langchain-ai/react-agent)
- [langchain-ai/memory-agent](https://github.com/langchain-ai/memory-agent)
- [agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit)
- [Awesome LangGraph & LangChain Ecosystem](https://github.com/vonzosten/awesome-LangGraph)
- [TradingAgents](https://github.com/TauricResearch/TradingAgents)

### Articles

- [LangGraph: Pregel for Agents - Inside langchain-ai/langgraph](https://pyshine.com/langgraph)
- [LangGraph Tutorial: Build a ReAct Agent With the v1.0 API](https://agentsindex.ai/blog/langgraph-tutorial)
- [Building Your First LangGraph Pipeline: A Decision-Maker's Guide](https://dev.to/labyrinthanalytics/building-your-first-langgraph-pipeline-a-decision-makers-guide-4e25)

### Questions and answers

- [langgraph issues: interrupt and resume](https://github.com/langchain-ai/langgraph/issues?q=is%3Aissue+interrupt)
- [langgraph issues: reducers and add_messages](https://github.com/langchain-ai/langgraph/issues?q=is%3Aissue+add_messages)
- [langgraph issues: subgraphs, Command and streaming](https://github.com/langchain-ai/langgraph/issues?q=is%3Aissue+subgraph)
- [langchain-ai/langgraph: most-reacted issues](https://github.com/langchain-ai/langgraph/issues?q=sort%3Areactions-%2B1-desc)
- [Merge message issues when LangGraph is called in parallel](https://forum.langchain.com/t/seeking-help-with-some-merge-message-issues-when-langgraph-is-called-in-parallel/3007)
- [Best practices for parallel nodes (fanouts)](https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900)

### Papers and specifications

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Pregel: A System for Large-Scale Graph Processing](https://cs.princeton.edu/courses/archive/spring16/cos598F/pregel_paper.pdf)
- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)

### Talks and workshops

- [LangChain: LangSmith Agent Lifecycle Workshop (official workshop repo)](https://github.com/langchain-ai/langsmith-agent-lifecycle-workshop)

### University courses

- [Agentic Artificial Intelligence (26CSC348) - Amrita Vishwa Vidyapeetham](https://amrita.edu/course/agentic-artificial-intelligence)
- [CS294/194-196: Agentic AI (UC Berkeley, Fall 2025)](https://rdi.berkeley.edu/agentic-ai/f25)
- [Stanford CS329A: Self-Improving AI Agents (Autumn 2025)](https://cs329a.stanford.edu)

### Books and courses

- [Introduction to LangGraph - Python (LangChain Academy)](https://academy.langchain.com/courses/intro-to-langgraph)
- [Project: Ambient Agents with LangGraph (LangChain Academy)](https://academy.langchain.com/courses/ambient-agents)
- [Long-Term Agentic Memory With LangGraph (DeepLearning.AI)](https://deeplearning.ai/courses/long-term-agentic-memory-with-langgraph)
- [AI Agents in LangGraph (DeepLearning.AI)](https://deeplearning.ai/courses/ai-agents-in-langgraph)

# Glossary

Terms used in the course, in alphabetical order.

## @entrypoint

The langgraph.func decorator that turns a function with one positional input into a Pregel object with a single node, so it can be invoked, streamed and checkpointed like a compiled graph.

*Also: entrypoint, entrypoints*

First used in [9.1](9-functional-api/9.1-entrypoint-and-task/README.md)

## @task

The langgraph.func decorator for a unit of work inside an entrypoint. Calling a task schedules it and returns a future at once, and with a checkpointer its result is saved so a resumed run does not run it again.

First used in [9.1](9-functional-api/9.1-entrypoint-and-task/README.md)

## `__interrupt__`

The extra key a default (v1) invoke() result contains when the run paused. In invoke() it holds a list of Interrupt objects; the key is absent when the run finished.

First used in [6.1](6-human-in-the-loop/6.1-interrupt-and-resume/README.md)

## `__previous__`

The internal channel of an entrypoint's graph that stores, in each checkpoint, the value the next run receives as previous. A plain return writes the return value to it; entrypoint.final writes its save part.

First used in [9.2](9-functional-api/9.2-functional-memory-interrupts/README.md)

## add_messages

The LangGraph reducer for message lists. It converts updates to message objects, gives each message without an id a new uuid, appends messages with new ids, replaces messages whose id is already in the list, and deletes the ones named by a RemoveMessage.

First used in [4.1](4-agents/4.1-messages-state/README.md)

## agent as a tool

A compiled agent wrapped in a tool function: the calling model writes the tool's arguments, the function invokes the agent with them and returns part of its result, usually the final message's text, as the tool result.

*Also: agents as tools*

First used in [8.4](8-multi-agent/8.4-supervisor-agents/README.md)

## agent loop

A cycle in which a model node either asks for tools or answers: requested tools run, their results go back to the model, and the cycle repeats until the model replies without tool calls.

*Also: agent loops*

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## agent middleware

Objects passed to create_agent with middleware=[...] that hook into the prebuilt loop: before or after each model call, around each model or tool call, or once per run. Node-style hooks become extra nodes in the compiled graph.

First used in [4.3](4-agents/4.3-create-agent/README.md)

## Agent Server

The HTTP server for LangGraph applications, the langgraph-api package. It serves the graphs from langgraph.json as assistants and adds threads, runs, a task queue and persistence of its own.

First used in [10.6](10-production/10.6-local-server/README.md)

## AgentState

The state schema of create_agent, imported from langchain.agents: messages with the add_messages reducer, structured_response (filled only with response_format) and a private jump_to key used by middleware.

First used in [4.3](4-agents/4.3-create-agent/README.md)

## AIMessageChunk

A piece of an AIMessage that a chat model yields while it streams. Chunks of one reply share the message id, and adding them with + joins them into the full message.

*Also: AIMessageChunks*

First used in [7.3](7-streaming/7.3-streaming-llm-tokens/README.md)

## approve-or-reject pattern

A human-in-the-loop pattern in which a node pauses with interrupt(), and the human's answer decides which node runs next, usually through a Command(goto=...) returned by the same node.

First used in [6.2](6-human-in-the-loop/6.2-interrupt-patterns/README.md)

## as_node

The update_state argument that names the node an update pretends to come from. The values go through that node's writers and reducers, and the graph continues along that node's edges; without it LangGraph infers the node that wrote last.

First used in [6.5](6-human-in-the-loop/6.5-time-travel/README.md)

## assistant_id

The id a client passes to the Agent Server to choose the configured graph a run uses. The server creates one assistant per graph in langgraph.json and also accepts the graph id as an assistant_id.

First used in [10.6](10-production/10.6-local-server/README.md)

## autocommit

A connection mode in which every SQL statement is committed on its own, with no transaction left open. The Postgres checkpointer and store need it, because their setup() runs CREATE INDEX CONCURRENTLY, which Postgres refuses inside a transaction.

First used in [5.6](5-persistence/5.6-postgres-persistence/README.md)

## back edge

An edge that leads from a node back to a node that already ran earlier in the same run, which closes a cycle in the graph.

*Also: back edges*

First used in [1.3](1-foundations/1.3-loops-and-recursion-limit/README.md)

## BaseCheckpointSaver

The abstract base class in langgraph.checkpoint.base that every checkpointer implements, with methods such as put, put_writes, get_tuple and list and their async versions.

First used in [5.1](5-persistence/5.1-checkpointers-and-threads/README.md)

## BaseStore

The abstract base class in langgraph.store.base for LangGraph's key-value stores of cross-thread memory, with methods such as put, get, search, delete and list_namespaces and their async versions.

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## BinaryOperatorAggregate

The LangGraph channel type for a key with a reducer. It starts from an empty value of the key's type, such as [] for a list, and calls the reducer with the stored value and each update.

First used in [2.2](2-state/2.2-reducers/README.md)

## bind_tools

A chat model method that returns a runnable which sends the given tools' schemas (name, description, argument types) with every request, so the model can answer with tool calls.

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## cache key

The value that decides whether a cached node result can be reused. LangGraph builds it from the node name and a hash of what the CachePolicy's key_func returns for the node's input; equal keys share one entry.

*Also: cache keys*

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## CachePolicy

The LangGraph setting, passed as cache_policy= to add_node, that lets a node's writes be reused instead of running it again. key_func turns the node's input into the cache key and ttl sets how many seconds an entry lives; it only takes effect when the graph is compiled with a cache backend.

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## callback handler

An object that LangChain notifies about events of a run, such as a chat model call starting, producing a new token or ending. Handlers passed in a run's config reach every model call made inside it.

*Also: callback handlers*

First used in [7.3](7-streaming/7.3-streaming-llm-tokens/README.md)

## chat model

A LangChain model that takes a list of messages and returns an AIMessage. Every provider integration, and the fake models used for tests, implement the same BaseChatModel interface, so one can replace another.

*Also: chat models*

First used in [4.1](4-agents/4.1-messages-state/README.md)

## ChatModelStream

The langchain-core object that represents one chat model call in a v3 run stream; it exposes the node that made the call, the text deltas (text), reasoning, tool calls and the assembled AIMessage (output).

*Also: ChatModelStreams*

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## checkpoint

A saved snapshot of a graph run: the values of all state channels, the nodes that run next and metadata such as step and source, stored under a thread_id. LangGraph writes one at every super-step boundary.

*Also: checkpoints*

First used in [5.1](5-persistence/5.1-checkpointers-and-threads/README.md)

## checkpoint_id

The id of one saved checkpoint, kept in config['configurable'] next to thread_id and checkpoint_ns. A config with a checkpoint_id points at that checkpoint instead of the newest one of the thread.

First used in [6.5](6-human-in-the-loop/6.5-time-travel/README.md)

## checkpoint_ns

The key in config['configurable'] that holds the namespace of a checkpoint: an empty string for the top-level graph, and the subgraph namespace, such as "billing:<task_id>", for checkpoints a subgraph saves.

First used in [8.1](8-multi-agent/8.1-subgraphs-shared-state/README.md)

## checkpointer

An object passed to compile(checkpointer=...) that saves the graph's state as checkpoints, keyed by thread_id, and loads a thread's latest checkpoint at the start of each run. Every checkpointer implements BaseCheckpointSaver.

*Also: checkpointers*

First used in [5.1](5-persistence/5.1-checkpointers-and-threads/README.md)

## Command

A LangGraph object a node can return instead of a dict. Its update is applied to the state like a normal node's return value, and its goto names the node or nodes to run in the next super-step.

First used in [3.3](3-control-flow/3.3-command/README.md)

## Command.PARENT

The constant "__parent__" for the graph field of a Command. It addresses the command to the closest parent graph: goto names a node of the parent, and the update is applied to the parent's state with the parent's reducers.

First used in [8.3](8-multi-agent/8.3-agent-handoffs/README.md)

## CompiledStateGraph

The runnable graph that StateGraph.compile() returns. It has invoke(), stream() and get_graph(), and its structure no longer changes.

*Also: compiled graph, compiled graphs*

First used in [1.1](1-foundations/1.1-hello-graph/README.md)

## conditional edge

An edge whose destination is chosen at run time: after its source node finishes, LangGraph calls a routing function and follows only the path it picks.

*Also: conditional edges*

First used in [1.2](1-foundations/1.2-conditional-edges/README.md)

## conftest.py

A file pytest loads before the tests in its directory and below. Fixtures defined in it are available to those tests without an import.

First used in [10.5](10-production/10.5-testing-graphs/README.md)

## ConnectionPool

The psycopg_pool class that keeps several open Postgres connections and lends one to each operation, replacing connections that broke. PostgresSaver and PostgresStore accept one in place of a single connection.

*Also: connection pool, connection pools*

First used in [5.6](5-persistence/5.6-postgres-persistence/README.md)

## context engineering

Deciding deliberately which information an agent or model receives, for example which messages pass from one agent to the next during a handoff.

First used in [8.3](8-multi-agent/8.3-agent-handoffs/README.md)

## context isolation

Running an agent on a fresh input that holds only what its caller passes, so it never sees the caller's conversation, and the caller sees only the result it returns, not the agent's intermediate messages.

First used in [8.4](8-multi-agent/8.4-supervisor-agents/README.md)

## context window

The largest input a model accepts in one request, measured in tokens; the system prompt, the messages and the tool schemas all count towards it.

*Also: context windows*

First used in [5.3](5-persistence/5.3-message-history/README.md)

## context_schema

The StateGraph argument that declares the type of the runtime context: a dataclass, a Pydantic model or a TypedDict. It adds no channels; LangGraph uses it for get_context_jsonschema() and to turn a dict context into an instance of a dataclass or Pydantic schema.

First used in [2.4](2-state/2.4-runtime-context/README.md)

## cooperative cancellation

Stopping an asyncio task by raising CancelledError at the await it is waiting on. It only takes effect when the code reaches an await, so blocking calls and threads cannot be stopped this way.

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## cosine similarity

A measure of how closely two vectors point the same way: their dot product divided by the product of their lengths. 1.0 means the same direction, 0.0 means no shared direction; it is undefined for a zero vector.

First used in [5.5](5-persistence/5.5-semantic-memory-search/README.md)

## create_agent

The langchain function (from langchain.agents) that builds and compiles a tool-calling agent from a model, a list of tools and options such as system_prompt and middleware. It returns an ordinary CompiledStateGraph with a model node and a tools node.

First used in [4.3](4-agents/4.3-create-agent/README.md)

## create_react_agent

The prebuilt agent function of langgraph.prebuilt before LangGraph 1.0. It is deprecated since 1.0 and will be removed in 2.0; use create_agent from langchain.agents instead, with system_prompt in place of prompt.

First used in [4.3](4-agents/4.3-create-agent/README.md)

## default_retry_on

The function RetryPolicy uses when retry_on is not given. It retries ConnectionError, 5xx errors from httpx, any requests.HTTPError that carries an error response (4xx included), and any exception not in its list of programming and OS errors (ValueError, TypeError, LookupError, OSError and others).

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## deferred node

A node added with add_node(..., defer=True). When triggered, it waits until no other task is pending anywhere in the graph and then runs once.

*Also: deferred nodes*

First used in [3.1](3-control-flow/3.1-parallel-branches/README.md)

## deterministic replay

The requirement that an entrypoint body, when it runs again from its first line on a resume, takes the same path and makes the same task calls in the same order as before, so each call is matched with its saved result. Time, randomness and I/O go into tasks to keep it.

First used in [9.2](9-functional-api/9.2-functional-memory-interrupts/README.md)

## disable_streaming

A field of every LangChain chat model. When True, the model never generates its reply in chunks, so even under messages mode it delivers the whole reply as one message.

First used in [7.3](7-streaming/7.3-streaming-llm-tokens/README.md)

## durability mode

The durability argument of invoke and stream ("sync", "async" or "exit") that decides when a run's checkpoints reach the checkpointer: before each next step, in the background during the next step (the default), or only once when the run ends.

*Also: durability modes*

First used in [5.2](5-persistence/5.2-sqlite-checkpointer/README.md)

## eager streaming

A stream() setting in which each chunk is handed to the caller as soon as it is produced, while the node is still running, instead of at the end of the step. Requesting the "custom" or "messages" mode, or subgraphs=True, turns it on.

First used in [7.2](7-streaming/7.2-custom-stream-data/README.md)

## embedding

A list of numbers (a vector) that represents a text so that texts with similar meaning get vectors pointing in similar directions. An embedding model or function turns texts into embeddings.

*Also: embeddings*

First used in [5.5](5-persistence/5.5-semantic-memory-search/README.md)

## embedding function

A function that takes a list of texts and returns one vector of the same length per text. A LangGraph store accepts such a plain function as the embed value of its index config.

*Also: embedding functions*

First used in [5.5](5-persistence/5.5-semantic-memory-search/README.md)

## EmptyInputError

The langgraph.errors exception raised when a graph is invoked with None as input on a thread that has no checkpoint, so there is neither new input nor saved work to continue.

First used in [10.4](10-production/10.4-recover-failed-run/README.md)

## END

The LangGraph constant for the virtual exit node of a graph (string value __end__). When a run reaches END, the graph stops and returns the final state.

First used in [1.1](1-foundations/1.1-hello-graph/README.md)

## entrypoint.final

A value an entrypoint can return to split its result in two: value goes to the caller and to get_state, save is stored in the checkpoint and becomes previous on the thread's next run. Annotate the function with entrypoint.final[ReturnType, SaveType].

First used in [9.2](9-functional-api/9.2-functional-memory-interrupts/README.md)

## error-handler node

The graph node LangGraph creates for a node-level error handler, named __error_handler__<node> for a per-node handler and __default_error_handler__ for the default one. It shows up under that name in streamed updates and in the compiled graph's nodes.

*Also: error-handler nodes*

First used in [10.3](10-production/10.3-error-handlers/README.md)

## exponential backoff

A retry schedule in which each wait is a fixed factor longer than the previous one, for example 0.5, 1, 2, 4 seconds, so that a struggling service gets more and more time to recover.

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## fail closed

A design rule for checks: when the input is missing, unclear or unexpected, take the safe default (deny, do nothing) instead of the risky action. An approval that fails closed acts only on an explicit yes.

*Also: fails closed, failing closed*

First used in [6.4](6-human-in-the-loop/6.4-interrupts-in-tools/README.md)

## fan-in

The point where parallel branches come together again in one node that combines their results.

First used in [3.1](3-control-flow/3.1-parallel-branches/README.md)

## fan-out

A point where one node, or START, leads to several nodes at once, so that all of them run in parallel in the same super-step. In LangGraph it is made by adding several plain edges from the same source.

*Also: fan-outs*

First used in [3.1](3-control-flow/3.1-parallel-branches/README.md)

## fixture scope

How long pytest keeps one value of a fixture: function (the default, a new value per test), class, module, package or session. A wider scope shares one object between tests.

*Also: fixture scopes*

First used in [10.5](10-production/10.5-testing-graphs/README.md)

## from_conn_string

A classmethod of database checkpointers such as SqliteSaver that works as a context manager: it opens the database connection, yields a saver that uses it and closes the connection when the with block ends.

First used in [5.2](5-persistence/5.2-sqlite-checkpointer/README.md)

## Functional API

The LangGraph API in which a workflow is an ordinary Python function decorated with @entrypoint that calls @task functions; control flow is plain Python and there is no state schema or explicit graph.

First used in [9.1](9-functional-api/9.1-entrypoint-and-task/README.md)

## GenericFakeChatModel

A chat model from langchain-core for offline runs and tests. It ignores its input and returns the next item of the iterator passed as messages, one per call.

First used in [4.1](4-agents/4.1-messages-state/README.md)

## get_state

The compiled graph method that reads a thread's latest checkpoint (or the one named by checkpoint_id) and returns it as a StateSnapshot, without running anything.

First used in [5.1](5-persistence/5.1-checkpointers-and-threads/README.md)

## get_state_history

A compiled graph method that yields a StateSnapshot for every saved checkpoint of a thread, newest first. It accepts filter, before and limit to narrow the list.

First used in [6.5](6-human-in-the-loop/6.5-time-travel/README.md)

## get_stream_writer

The function in langgraph.config that returns the stream writer of the run currently executing the node or task. Outside a run it raises RuntimeError.

*Also: get_stream_writer()*

First used in [7.2](7-streaming/7.2-custom-stream-data/README.md)

## get_subgraphs

The compiled graph method that yields (name, subgraph) pairs for the subgraphs LangGraph can find without running anything: compiled graphs added as nodes, and compiled graphs a function node refers to through a global or closure variable. Subgraphs compiled with checkpointer=False are skipped.

First used in [8.2](8-multi-agent/8.2-subgraphs-own-state/README.md)

## goto

The field of a Command that names where the graph goes next: a node name, a list of names, a Send or END. LangGraph treats it as one more edge that fires, in addition to the node's static edges.

First used in [3.3](3-control-flow/3.3-command/README.md)

## Graph API

The LangGraph API in which a workflow is declared as a StateGraph: a state schema, nodes that update it and edges between them, compiled into a runnable graph.

First used in [9.1](9-functional-api/9.1-entrypoint-and-task/README.md)

## graph factory

A function that langgraph.json names instead of a compiled graph. The server calls it each time it needs the graph, and passes the run's config, a ServerRuntime, both or nothing, depending on the function's parameters.

*Also: graph factories*

First used in [10.6](10-production/10.6-local-server/README.md)

## GraphBubbleUp

The base class in langgraph.errors for exceptions LangGraph uses to stop a run on purpose, such as GraphInterrupt. It subclasses Exception, so a bare except Exception also catches it.

First used in [6.3](6-human-in-the-loop/6.3-rules-of-interrupts/README.md)

## GraphInterrupt

The exception interrupt() raises internally to stop a node. LangGraph catches it, saves the pending task with its Interrupt object and ends the run normally, so the caller never sees the exception.

First used in [6.1](6-human-in-the-loop/6.1-interrupt-and-resume/README.md)

## GraphOutput

The object that invoke() returns when called with version="v2" (LangGraph 1.1 and later). Its value attribute holds the final state, built as the schema class for dataclass and Pydantic schemas, and its interrupts attribute holds a tuple of interrupts.

First used in [2.1](2-state/2.1-state-schemas/README.md)

## GraphRecursionError

The exception from langgraph.errors that a run raises when it reaches its recursion_limit before the graph has finished. It is a subclass of Python's RecursionError.

First used in [1.3](1-foundations/1.3-loops-and-recursion-limit/README.md)

## GraphRunStream

The object stream_events(version="v3") returns: one lazy graph run with typed projections (values, messages, extensions), the final output and interrupt status as properties, and the raw protocol events when iterated directly.

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## handoff

A transfer of control in which the agent that is working decides itself which other agent takes over, and passes along the state the next agent needs. In LangGraph a node inside an agent's subgraph does it by returning a Command with graph=Command.PARENT.

*Also: handoffs*

First used in [8.3](8-multi-agent/8.3-agent-handoffs/README.md)

## heartbeat

A call to runtime.heartbeat() inside a node, which tells LangGraph that the current attempt is still making progress and resets its idle_timeout. Outside an attempt with an idle timeout it does nothing.

*Also: heartbeats*

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## human-in-the-loop

A workflow in which a running graph stops at a chosen point, hands information to a person, and continues with that person's answer. In LangGraph it is built with interrupt() and Command(resume=...) on a checkpointed graph.

*Also: HITL*

First used in [6.1](6-human-in-the-loop/6.1-interrupt-and-resume/README.md)

## HumanInTheLoopMiddleware

The prebuilt agent middleware in langchain.agents.middleware that pauses a create_agent agent with interrupt() before configured tool calls run, so a person can approve, edit or reject them or answer in the tool's place.

First used in [6.4](6-human-in-the-loop/6.4-interrupts-in-tools/README.md)

## idempotent

Said of an operation that has the same effect whether it runs once or several times, such as an upsert or a send guarded by an idempotency key. Code before interrupt() must be idempotent, because a resumed node runs again from its first line.

*Also: idempotency*

First used in [6.3](6-human-in-the-loop/6.3-rules-of-interrupts/README.md)

## idle_timeout

The limit of a TimeoutPolicy, in seconds, on how long one node attempt may go without a progress signal. Each progress signal starts the count again.

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## IndexConfig

The TypedDict from langgraph.store.base that turns on semantic search in a store. Its keys are dims (vector length), embed (the embedding model or function) and fields (which parts of a value are embedded).

First used in [5.5](5-persistence/5.5-semantic-memory-search/README.md)

## injectable parameter

A parameter of an entrypoint function that LangGraph fills in at run time, recognised by its name: previous, config, store, writer or runtime. The caller never passes it; it is declared after the single input, usually as keyword-only.

*Also: injectable parameters*

First used in [9.2](9-functional-api/9.2-functional-memory-interrupts/README.md)

## InjectedToolCallId

An annotation from langchain_core.tools for a tool parameter that ToolNode fills in with the id of the current tool call. The parameter is left out of the schema the model sees, so the model never supplies it.

First used in [6.4](6-human-in-the-loop/6.4-interrupts-in-tools/README.md)

## InMemoryCache

The cache backend from langgraph.cache.memory that keeps cached node writes in a dict in process memory. It is passed to compile(cache=...) and is empty again after a restart.

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## InMemorySaver

The checkpointer from langgraph.checkpoint.memory that keeps all checkpoints in a dictionary inside the Python object, so they are lost when the object or the process goes away. MemorySaver is an older alias of the same class.

First used in [5.1](5-persistence/5.1-checkpointers-and-threads/README.md)

## InMemoryStore

The BaseStore implementation in langgraph.store.memory that keeps items in Python dicts inside the object. It is meant for development and tests: everything is lost when the process exits.

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## input schema

A schema that limits what is read in. A graph's input schema (StateGraph's input_schema) lists the keys that invoke() accepts, and other keys are dropped; a node's input schema, usually taken from its first parameter's type hint, lists the keys the node receives.

*Also: input schemas*

First used in [2.3](2-state/2.3-input-output-schemas/README.md)

## Interrupt object

The record of one pending pause, an instance of langgraph.types.Interrupt. Its value holds the payload passed to interrupt() and its id identifies the interrupt; response_schema is None unless one was given.

*Also: Interrupt objects*

First used in [6.1](6-human-in-the-loop/6.1-interrupt-and-resume/README.md)

## interrupt()

The function from langgraph.types that pauses a graph inside a node. On the first call it stops the run and hands its payload to the caller; when the thread is resumed, the node runs again and the same call returns the resume value instead.

First used in [6.1](6-human-in-the-loop/6.1-interrupt-and-resume/README.md)

## interrupt_after

A list of node names, given to compile() or to a single invoke() or stream() call, after which the run pauses and saves a checkpoint, a static breakpoint. compile() rejects unknown names; the per-call argument silently ignores them.

First used in [10.5](10-production/10.5-testing-graphs/README.md)

## InvalidNamespaceError

The ValueError subclass a store raises for a bad namespace: an empty label, a label that is not a string or contains a period, and, for put, an empty namespace or the root label "langgraph".

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## InvalidUpdateError

The LangGraph exception for an update that cannot be applied, for example when two nodes write a key without a reducer in the same step, or when a node returns something other than a dict.

First used in [2.2](2-state/2.2-reducers/README.md)

## jitter

A random amount added to each retry wait, so that many clients that failed at the same moment do not all retry at the same moment again. In LangGraph 1.2.16, RetryPolicy(jitter=True) adds 0 to 1 second to every wait.

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## JsonPlusSerializer

The default checkpoint serializer from langgraph-checkpoint. It turns state values such as messages, primitives, datetimes and dataclasses into msgpack bytes and raises TypeError for objects it does not know.

First used in [5.2](5-persistence/5.2-sqlite-checkpointer/README.md)

## LangChainBetaWarning

The warning langchain-core emits when code uses an API marked @beta; it subclasses DeprecationWarning and is shown by default because importing langchain_core installs a filter for it.

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## langgraph dev

The langgraph-cli command that runs the Agent Server for development in the current Python process, with an in-memory runtime, reload on code changes and no Docker. It reads langgraph.json from the working directory.

First used in [10.6](10-production/10.6-local-server/README.md)

## langgraph.json

The manifest of a LangGraph application. It maps each graph id to the file and object the server loads, lists the dependencies to install, and can name an env file and the Python version used for images.

First used in [10.6](10-production/10.6-local-server/README.md)

## langgraph_node

The metadata key that names the graph node in which a chat model call ran. Messages mode puts it in the metadata of every token, so the caller can filter the stream by node.

First used in [7.3](7-streaming/7.3-streaming-llm-tokens/README.md)

## langgraph_sdk

The Python client for the Agent Server's HTTP API. get_client returns an async client and get_sync_client a sync one, each with sub-clients such as assistants, threads and runs.

First used in [10.6](10-production/10.6-local-server/README.md)

## LastValue

The LangGraph channel type for a state key without a reducer. It stores the one value written in a super-step and raises InvalidUpdateError if it receives more than one.

First used in [3.1](3-control-flow/3.1-parallel-branches/README.md)

## lax mode

Pydantic's default validation mode, in which a value of a compatible type is converted to the declared type, for example the string "3" to the int 3 for an int field. Strict mode turns this conversion off and rejects such values.

First used in [2.1](2-state/2.1-state-schemas/README.md)

## long-term memory

Information an application keeps across conversations, such as a user's preferences, so that any later thread can use it. In LangGraph it lives in a store, not in the checkpointed state.

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## managed value

A state key whose value LangGraph computes itself before each node or routing function call instead of storing it in a channel. Nodes cannot write it, the caller does not pass it, and it is left out of the result.

*Also: managed values*

First used in [1.3](1-foundations/1.3-loops-and-recursion-limit/README.md)

## map-reduce

A pattern that splits work into independent pieces, processes each piece in its own parallel task (map), then combines the results in one step (reduce). In LangGraph the map is usually a list of Send objects and the reduce a reducer plus one node that reads the collected results.

*Also: Map-Reduce*

First used in [3.2](3-control-flow/3.2-map-reduce-send/README.md)

## max_concurrency

A top-level run config key that limits how many tasks of a run execute at the same time. In synchronous runs it sets the size of the thread pool used for the whole run; in async runs it is the size of a semaphore.

First used in [3.2](3-control-flow/3.2-map-reduce-send/README.md)

## message id

The id field of a LangChain message. add_messages uses it to decide whether an update is a new message or a replacement, so ids must be unique within a conversation.

*Also: message ids*

First used in [4.1](4-agents/4.1-messages-state/README.md)

## messages mode

The stream mode stream_mode="messages": LangGraph forwards each token a LangChain chat model produces inside a node to the caller as an (AIMessageChunk, metadata) pair, plus messages that nodes return in their updates.

*Also: message mode*

First used in [7.3](7-streaming/7.3-streaming-llm-tokens/README.md)

## MessagesState

A ready-made LangGraph state schema, a TypedDict with one key, messages, typed as a list of AnyMessage and reduced by add_messages. Subclass it to add more keys.

First used in [4.1](4-agents/4.1-messages-state/README.md)

## node-level error handler

A function passed as error_handler to add_node (or as a default to set_node_defaults) that LangGraph runs once after a node fails for good, when its retries are used up or the error is not retried. It gets the node's input state and a NodeError, and its return value, usually a Command with goto, decides how the run continues.

*Also: node-level error handlers*

First used in [10.3](10-production/10.3-error-handlers/README.md)

## node_attempt

The field of runtime.execution_info that holds the number of the current attempt of a node: 1 on the first run, then 2, 3 and so on for each retry.

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## NodeError

A frozen dataclass from langgraph.errors that LangGraph passes to a node-level error handler with a parameter annotated NodeError. Its field node is the name of the failed node and error is the last exception it raised.

First used in [10.3](10-production/10.3-error-handlers/README.md)

## NodeTimeoutError

The langgraph.errors exception raised when an attempt of a node exceeds its run_timeout or idle_timeout. Its fields node, kind ("idle" or "run"), timeout and elapsed say what fired, and it is not a subclass of the built-in TimeoutError.

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## output coercion

With version="v2", LangGraph builds the final output by calling the dataclass or Pydantic state schema on the stored values, so the result is an instance of that class with defaults filled in and, for Pydantic, values validated.

First used in [2.1](2-state/2.1-state-schemas/README.md)

## output schema

The schema passed as StateGraph's output_schema. It lists the keys that invoke() returns at the end of a run; it defaults to the state schema.

*Also: output schemas*

First used in [2.3](2-state/2.3-input-output-schemas/README.md)

## Overwrite

A wrapper from langgraph.types. A node returns Overwrite(value) for a key that has a reducer to store value as it is, skipping the reducer, for example to reset an accumulated list.

First used in [2.2](2-state/2.2-reducers/README.md)

## pairing rule

The requirement, enforced by most chat model providers, that every tool call in a conversation history is answered by a ToolMessage with the same tool_call_id before the model is called again.

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## parent graph

The graph that contains a subgraph as one of its nodes or calls it from a node. Its state, reducers and checkpointer decide what happens to the subgraph's result.

*Also: parent graphs*

First used in [8.1](8-multi-agent/8.1-subgraphs-shared-state/README.md)

## ParentCommand

The exception from langgraph.errors, a GraphBubbleUp, that carries a Command addressed to a parent graph. LangGraph raises it when a node returns Command(graph=Command.PARENT); the parent's task for the subgraph node catches it and applies the command.

First used in [8.3](8-multi-agent/8.3-agent-handoffs/README.md)

## partial execution

Running only a section of a graph in a test: seed a thread with update_state(as_node=...) as if the node before the section had just run, then invoke with None and interrupt_after set to the section's last node.

First used in [10.5](10-production/10.5-testing-graphs/README.md)

## partial update

The dict a node returns: only the state keys it wants to change. LangGraph merges it into the shared state and leaves all other keys as they were.

*Also: partial updates*

First used in [1.1](1-foundations/1.1-hello-graph/README.md)

## path map

The optional third argument of add_conditional_edges: a dict from the labels a routing function returns to node names. It also declares every possible destination, so compile() can check them and the graph can be drawn.

*Also: path maps*

First used in [1.2](1-foundations/1.2-conditional-edges/README.md)

## pending writes

The saved outputs of single tasks of a super-step whose closing checkpoint is not written yet. They let a resumed run reuse work that already finished instead of running those tasks again.

First used in [5.2](5-persistence/5.2-sqlite-checkpointer/README.md)

## per-invocation persistence

The default persistence mode of a subgraph compiled with checkpointer=None: it saves into the parent's checkpointer under a namespace that includes the task id, so each run starts a fresh history that lasts long enough to pause and resume.

First used in [8.2](8-multi-agent/8.2-subgraphs-own-state/README.md)

## per-thread persistence

The persistence mode of a subgraph compiled with checkpointer=True: it saves under a fixed namespace on the thread, so its state carries over from one call to the next on the same thread.

First used in [8.2](8-multi-agent/8.2-subgraphs-own-state/README.md)

## permanent error

A failure caused by the request itself or by a bug, such as invalid input, a missing record or a 4xx answer, so sending the same request again fails the same way. Retrying it only wastes time.

*Also: permanent errors*

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## pgvector

A Postgres extension that adds a vector column type of fixed length and distance operators such as <=> for cosine distance. PostgresStore with an index needs it installed in the database server.

First used in [5.6](5-persistence/5.6-postgres-persistence/README.md)

## PostgresSaver

The checkpointer from the langgraph-checkpoint-postgres package that keeps checkpoints in Postgres tables. It works on one psycopg connection or a ConnectionPool, and its tables are created by calling setup().

First used in [5.6](5-persistence/5.6-postgres-persistence/README.md)

## PostgresStore

The BaseStore implementation from langgraph-checkpoint-postgres that keeps items in a Postgres table. With index= it also stores each item's embedding in a pgvector column for semantic search. Its tables are created by calling setup().

First used in [5.6](5-persistence/5.6-postgres-persistence/README.md)

## Pregel

The class in langgraph.pregel that runs every LangGraph workflow in super-steps. StateGraph.compile() returns a subclass of it, and @entrypoint returns a Pregel object directly.

First used in [9.1](9-functional-api/9.1-entrypoint-and-task/README.md)

## PregelNode

The object a compiled graph keeps for each node in its nodes mapping. Its invoke() runs only the node's function on the given input and returns the node's update, without writing it to any channel, following edges or saving a checkpoint.

*Also: PregelNodes*

First used in [10.5](10-production/10.5-testing-graphs/README.md)

## PregelTask

The named tuple that StateSnapshot.tasks holds for each task of the saved step, with the task's name, its error (a saved repr string, or None) and its result, the writes it produced if it finished.

*Also: PregelTasks*

First used in [10.4](10-production/10.4-recover-failed-run/README.md)

## previous parameter

The injectable parameter of an entrypoint that receives what the last finished run on the same thread saved: its return value, or the save part of entrypoint.final. It is None on a new thread and without a checkpointer.

First used in [9.2](9-functional-api/9.2-functional-memory-interrupts/README.md)

## private schema

A schema with keys that only some nodes use and that appear in neither the graph's input nor its output schema. It reaches the graph through a node's input schema, which registers its keys as channels.

*Also: private schemas*

First used in [2.3](2-state/2.3-input-output-schemas/README.md)

## progress signal

An event that resets a node's idle_timeout: a runtime.heartbeat() call and, with the default refresh_on="auto", also state writes, stream output, child-task scheduling and LangChain callback events from the node.

*Also: progress signals*

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## protocol event

One event of the v3 streaming protocol: a dict with type, a strictly increasing seq, the channel name in method, and params holding the namespace, a timestamp and the channel's data.

*Also: protocol events*

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## pytest fixture

A function marked with @pytest.fixture whose return value pytest passes to every test that names it as a parameter. By default it is called again for each test.

*Also: pytest fixtures*

First used in [10.5](10-production/10.5-testing-graphs/README.md)

## ReAct

Reason plus act: the agent pattern from Yao et al. (2022) in which a language model alternates reasoning steps with actions such as tool calls, and reads each action's result before deciding the next step.

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## recursion_limit

The run config key that caps how many super-steps one run of a LangGraph graph may take. When a run reaches it without finishing, LangGraph raises GraphRecursionError; in langgraph 1.2.16 the default is 10007.

First used in [1.3](1-foundations/1.3-loops-and-recursion-limit/README.md)

## reducer

A function of two arguments, the stored value and a node's update, that returns the new value of a state key. It is attached to a key with Annotated[type, reducer]; a key without one keeps the last value written.

*Also: reducers*

First used in [2.2](2-state/2.2-reducers/README.md)

## refresh_on

The TimeoutPolicy field that chooses which progress signals reset the idle_timeout: "auto" (the default) counts writes, stream output, child tasks, LangChain callbacks and heartbeats, "heartbeat" counts runtime.heartbeat() calls only.

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## RemainingSteps

A managed value from langgraph.managed. A state key annotated with it holds how many super-steps the current run has left before its recursion_limit, so a node or routing function can stop a loop in time.

First used in [1.3](1-foundations/1.3-loops-and-recursion-limit/README.md)

## RemoveMessage

A langchain-core message that, written to a key reduced by add_messages, deletes the stored message with the same id instead of being added. An id that is not in the list raises ValueError.

First used in [4.1](4-agents/4.1-messages-state/README.md)

## resume map

A dict passed as Command(resume={interrupt_id: value, ...}) that answers pending interrupts by their Interrupt.id. LangGraph 1.2.16 reads a resume dict as a resume map only when every key is a 32-character hex string.

*Also: resume maps*

First used in [6.3](6-human-in-the-loop/6.3-rules-of-interrupts/README.md)

## resume value

The value a caller passes as Command(resume=value) on the paused thread. LangGraph stores it with the thread and returns it from the interrupt() call that paused the node.

*Also: resume values*

First used in [6.1](6-human-in-the-loop/6.1-interrupt-and-resume/README.md)

## RetryPolicy

The LangGraph setting, passed as retry_policy= to add_node, that reruns a node when it raises a matching exception: up to max_attempts tries in total, with growing waits between them. When the attempts run out, the node's own exception reaches the caller.

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## review-and-edit pattern

A human-in-the-loop pattern in which the interrupt payload shows a proposed value, the human sends back a corrected version as the resume value, and the node writes that version into the state before the run continues.

First used in [6.2](6-human-in-the-loop/6.2-interrupt-patterns/README.md)

## routing function

The function passed to add_conditional_edges. It reads the state after the source node has run and returns a label or node name that says where the graph goes next; it does not update the state.

*Also: routing functions*

First used in [1.2](1-foundations/1.2-conditional-edges/README.md)

## run config

The RunnableConfig dict passed as the config argument of invoke() or stream(). It carries run mechanics such as recursion_limit, tags and, under its configurable key, thread_id, rather than the graph's own settings.

First used in [2.4](2-state/2.4-runtime-context/README.md)

## run_timeout

The hard wall-clock limit of a TimeoutPolicy, in seconds, counted from the start of one node attempt. Progress and heartbeats never extend it.

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## running summary

A summary of deleted messages kept in the graph state. Each summarization step extends it with the messages it is about to delete, so earlier messages never need to be read again.

*Also: running summaries*

First used in [5.3](5-persistence/5.3-message-history/README.md)

## runs.wait

The langgraph_sdk call that creates a run, blocks until it ends and returns the thread's final state values as JSON. A failed run comes back as a dict with an __error__ key.

First used in [10.6](10-production/10.6-local-server/README.md)

## runtime context

Read-only settings for one run of a LangGraph graph, passed with invoke(..., context=...) and read inside nodes as runtime.context. It is not part of the state: it adds no channels and is never returned or checkpointed.

*Also: run context*

First used in [2.4](2-state/2.4-runtime-context/README.md)

## schema migration

A numbered change to a database's tables or indexes that is applied once and recorded, so it is never applied twice. setup() of the Postgres checkpointer and store runs the migrations a database has not seen yet.

*Also: schema migrations*

First used in [5.6](5-persistence/5.6-postgres-persistence/README.md)

## SearchItem

The object a store's search returns for each match: an Item (namespace, key, value, created_at, updated_at) plus a score, which is None when no query was given.

*Also: SearchItems*

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## semantic search

Finding stored items by meaning rather than by exact key or field value: the query and the items are embedded, and the items whose vectors are most similar to the query vector come first.

First used in [5.5](5-persistence/5.5-semantic-memory-search/README.md)

## Send

A LangGraph object from langgraph.types that names a target node and carries an input for it. A conditional edge may return a list of Send objects; each becomes its own task of the next super-step, with the Send's argument as that task's input.

First used in [3.2](3-control-flow/3.2-map-reduce-send/README.md)

## set_node_defaults

A StateGraph method that sets a default retry_policy, timeout, cache_policy and error_handler for every node that does not set its own in add_node. The defaults are applied at compile(); retry and timeout also cover error-handler nodes, cache and error handler only regular nodes, and subgraphs do not inherit them.

*Also: set_node_defaults()*

First used in [10.3](10-production/10.3-error-handlers/README.md)

## shared key

A state key that a parent graph and a subgraph added as its node both declare under the same name. Only shared keys pass between the two graphs: the subgraph reads the parent's value as input, and its final value goes back to the parent through the parent's reducer.

*Also: shared keys*

First used in [8.1](8-multi-agent/8.1-subgraphs-shared-state/README.md)

## short-term memory

What a graph remembers within one conversation: the state of a single thread, saved by the checkpointer and gone for any other thread_id.

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## SqliteSaver

The LangGraph checkpointer from the separate langgraph-checkpoint-sqlite package that stores checkpoints in a SQLite database file, so threads survive the end of the process. Meant for local work and small projects.

First used in [5.2](5-persistence/5.2-sqlite-checkpointer/README.md)

## START

The LangGraph constant for the virtual entry node of a graph (string value __start__). An edge from START marks the node that receives the input first.

First used in [1.1](1-foundations/1.1-hello-graph/README.md)

## state schema

The type, usually a TypedDict, that lists the keys of a graph's shared state. LangGraph creates one channel per key and drops updates for keys that are not in it.

*Also: state schemas*

First used in [1.1](1-foundations/1.1-hello-graph/README.md)

## StateGraph

The LangGraph builder class for graphs whose nodes share one state. You give it a state schema, register nodes and edges on it, and call compile() to get a runnable graph.

First used in [1.1](1-foundations/1.1-hello-graph/README.md)

## StateSnapshot

The NamedTuple from langgraph.types that get_state returns for one checkpoint, with the fields values, next, config, metadata, created_at, parent_config, tasks and interrupts.

First used in [5.1](5-persistence/5.1-checkpointers-and-threads/README.md)

## store namespace

A tuple of strings, such as (user_id, "genres"), that groups items in a store the way a folder path groups files. Together with the key it addresses one item, and search matches it by prefix.

*Also: store namespaces*

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## stream projection

A typed view of one part of a v3 run stream, such as run.values or run.messages: a single-consumer cursor that a stream transformer fills from the run's protocol events.

*Also: stream projections*

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## stream transformer

A StreamTransformer subclass that reads a v3 run's protocol events and fills one or more projections; it declares the stream modes it needs in required_stream_modes, and only modes some transformer requests are produced.

*Also: stream transformers*

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## stream writer

The callable a node uses to send its own data into a running graph's stream: writer(value). It belongs to one run; when the caller did not request the "custom" stream mode, it is a function that does nothing.

*Also: stream writers*

First used in [7.2](7-streaming/7.2-custom-stream-data/README.md)

## stream_events

The compiled graph method that, with version="v3", returns a GraphRunStream for one run instead of an iterator of chunks; the run moves forward as the caller reads its projections. Experimental in LangGraph 1.2.16; astream_events is the async counterpart.

*Also: stream_events()*

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## stream_mode

The argument of stream() that chooses what each chunk carries, for example the full state after each step ("values") or what each node returned ("updates"). It takes one mode or a list of modes; a compiled StateGraph defaults to "updates".

*Also: stream mode, stream modes*

First used in [7.1](7-streaming/7.1-stream-modes/README.md)

## StreamChannel

The queue behind a v3 projection in langgraph.stream: it buffers items only after a consumer subscribes, allows a single subscriber, and offers tee(n) for several independent cursors.

First used in [7.4](7-streaming/7.4-event-streaming/README.md)

## StreamMessagesHandler

The LangChain callback handler that LangGraph attaches to a run streamed with "messages". It receives the chat model's tokens and the nodes' outputs and puts them on the run's stream.

First used in [7.3](7-streaming/7.3-streaming-llm-tokens/README.md)

## StreamPart

The dict that stream(version="v2") yields for every chunk, with the keys type (the stream mode), ns (the subgraph path, empty for the top-level graph) and data, plus interrupts on values parts. In langgraph.types it is a union of one TypedDict per stream mode.

*Also: StreamParts, stream part, stream parts*

First used in [7.1](7-streaming/7.1-stream-modes/README.md)

## subagent

An agent that another agent calls through a tool, as LangChain's docs name it in the supervisor pattern. It runs on the input the tool passes, returns a result to the calling agent and does not talk to the user.

*Also: subagents*

First used in [8.4](8-multi-agent/8.4-supervisor-agents/README.md)

## subgraph

A compiled graph used inside another graph, either added directly as a node or called from inside a node function. It runs as one task of the graph that contains it.

*Also: subgraphs*

First used in [8.1](8-multi-agent/8.1-subgraphs-shared-state/README.md)

## subgraph namespace

The path that identifies one run of a subgraph: one "node_name:<task_id>" entry per level of nesting. Streamed parts carry it as the tuple ns, () for the top-level graph, and checkpoints carry it as the string checkpoint_ns, with levels joined by "|".

*Also: subgraph namespaces*

First used in [8.1](8-multi-agent/8.1-subgraphs-shared-state/README.md)

## SummarizationMiddleware

The prebuilt agent middleware in langchain.agents.middleware that summarizes older messages of a create_agent agent once a trigger such as a message or token count is reached, and keeps the most recent messages.

First used in [5.3](5-persistence/5.3-message-history/README.md)

## super-step

One tick of the LangGraph runtime: every node scheduled for that tick runs, then all their updates are applied to the state together. Nodes that run one after another are in separate super-steps; nodes that run in parallel share one.

*Also: super-steps*

First used in [1.3](1-foundations/1.3-loops-and-recursion-limit/README.md)

## supervisor pattern

A multi-agent design in which one main agent, the supervisor, calls specialist agents as tools, gets their results back as tool results and alone decides what happens next and what the user is told.

First used in [8.4](8-multi-agent/8.4-supervisor-agents/README.md)

## system_prompt

The create_agent keyword argument that holds the system instruction, as a string or a SystemMessage. It is put in front of the messages on every model call and never stored in the state.

First used in [4.3](4-agents/4.3-create-agent/README.md)

## TAG_NOSTREAM

The constant in langgraph.constants whose value is the tag "nostream". A chat model call carrying this tag still runs, but messages mode does not stream its tokens.

*Also: nostream*

First used in [7.3](7-streaming/7.3-streaming-llm-tokens/README.md)

## thread_id

The key in config['configurable'] that names a conversation (a thread) for a checkpointed graph. Runs with the same thread_id continue from the same saved state; a new thread_id starts from empty state.

First used in [5.1](5-persistence/5.1-checkpointers-and-threads/README.md)

## time travel

Continuing a thread from one of its earlier checkpoints instead of the newest one: either replaying it unchanged with invoke(None, config) or forking it with update_state. Nodes before the checkpoint are not run again, nodes after it are.

First used in [6.5](6-human-in-the-loop/6.5-time-travel/README.md)

## TimeoutPolicy

The langgraph.types setting passed as add_node(..., timeout=...) that limits how long one attempt of an async node may take, with a hard run_timeout, an idle_timeout reset by progress, or both. A plain number or timedelta passed as timeout means a run_timeout only.

First used in [10.2](10-production/10.2-node-timeouts/README.md)

## tool call

A request from a chat model to run one tool: an entry in AIMessage.tool_calls with the tool's name, its arguments and a call id. The model only asks; the application runs the tool and sends the result back.

*Also: tool calls*

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## tool_call_id

The field of a ToolMessage that holds the id of the tool call it answers. It must equal the id of a tool call in an earlier AIMessage; that is how a result is matched to its request.

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## ToolMessage

The langchain-core message that carries the result of one tool call back to the model. Its tool_call_id names the call it answers, its content is the result as text, and its status is success or error.

*Also: ToolMessages*

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## ToolNode

A prebuilt LangGraph node (langgraph.prebuilt) that runs every tool call of the latest AIMessage in the state and returns one ToolMessage per call, in call order.

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## tools_condition

A prebuilt routing function from langgraph.prebuilt. It returns "tools" when the last message in the state has tool calls and "__end__" otherwise, so it is used as the conditional edge out of the model node.

First used in [4.2](4-agents/4.2-tool-calling-loop/README.md)

## transient error

A failure caused by a passing condition, such as a dropped connection, a 503 or a rate limit, so the same request can succeed when it is sent again a little later. These are the errors worth retrying.

*Also: transient errors*

First used in [10.1](10-production/10.1-retry-and-cache/README.md)

## trim_messages

A langchain_core.messages function that cuts a message list to a budget: it keeps the newest (strategy="last") or oldest messages whose size, measured by token_counter, fits max_tokens, and can make the result start or end on a given message type. It returns a new list and leaves its input unchanged.

First used in [5.3](5-persistence/5.3-message-history/README.md)

## update_state

A compiled graph method that writes a new checkpoint (source update) on top of the given one, with the values applied as if the node as_node had returned them, and returns the new checkpoint's config. It never changes the checkpoint it starts from.

First used in [6.5](6-human-in-the-loop/6.5-time-travel/README.md)

## upsert

A write that inserts a record if its key is new and replaces it if the key already exists. A store's put works this way for the same namespace and key.

*Also: upserts*

First used in [5.4](5-persistence/5.4-long-term-memory-store/README.md)

## v2 format

The output format chosen with version="v2" on stream(), astream(), invoke() and ainvoke(), opt-in since LangGraph 1.1: streams yield StreamPart dicts and invoke() returns a GraphOutput, with interrupts in their own field instead of an __interrupt__ key. The default is still v1.

*Also: v2 output format*

First used in [7.1](7-streaming/7.1-stream-modes/README.md)

## validation loop

A human-in-the-loop pattern that checks the resume value before using it and, when it is invalid, asks again with an explanation of what was wrong, usually by routing back to the asking node so that each run calls interrupt() once, until an acceptable answer arrives.

*Also: validation loops*

First used in [6.2](6-human-in-the-loop/6.2-interrupt-patterns/README.md)

## ValidationError

The exception Pydantic raises when data does not satisfy a model's types or constraints. With a Pydantic state schema, LangGraph lets it propagate out of invoke() when a node's input or the v2 output fails validation.

*Also: ValidationErrors*

First used in [2.1](2-state/2.1-state-schemas/README.md)

## waiting edge

An edge with a list of source nodes, made with add_edge([a, b, ...], target). The target runs once, only after every listed source has finished, however many super-steps each branch takes.

*Also: waiting edges*

First used in [3.1](3-control-flow/3.1-parallel-branches/README.md)

## wrapper node

A node function that calls a subgraph whose state schema differs from the parent's: it builds the subgraph's input from the parent state, invokes the subgraph, and returns a parent update made from the subgraph's result.

*Also: wrapper nodes*

First used in [8.2](8-multi-agent/8.2-subgraphs-own-state/README.md)

## xray

The keyword argument of get_graph() that expands subgraph nodes in the drawing. True expands every level, an int expands that many levels; inner node ids get the subgraph node's name as prefix, such as billing:find_invoice.

First used in [8.1](8-multi-agent/8.1-subgraphs-shared-state/README.md)

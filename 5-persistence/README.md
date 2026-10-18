# 5 Persistence and Memory

Saving state at every super-step with checkpointers: conversations per thread, durable storage in SQLite and Postgres, managing a growing history, and stores for memory that is shared across threads.

## Lessons

- [5.1 Checkpointers and Threads](5.1-checkpointers-and-threads/README.md) — Starts from a compact copy of the calculator agent and adds InMemorySaver, so it remembers earlier turns within a thread_id and starts fresh in another. Shows get_state and the StateSnapshot it returns.
- [5.2 Durable Checkpoints with SQLite](5.2-sqlite-checkpointer/README.md) — Swaps InMemorySaver for SqliteSaver so a conversation survives a process restart: the run is executed twice as separate processes on the same database file. Covers from_conn_string and the durability modes (exit, async, sync).
- [5.3 Trimming and Summarizing Message History](5.3-message-history/README.md) — Keeps a long conversation small: trims what is sent to the model with trim_messages, deletes old messages from state with RemoveMessage, and folds them into a running summary kept in the state.
- [5.4 Long-Term Memory with a Store](5.4-long-term-memory-store/README.md) — A reading-list assistant remembers a user's favourite genres across threads with InMemoryStore: namespaces per user, put, get and search, and runtime.store inside nodes, next to the per-thread checkpointer.
- [5.5 Semantic Search over Memories](5.5-semantic-memory-search/README.md) — Gives the store an embedding index so the assistant finds memories by meaning rather than by key. Uses a deterministic fake embedding so search results are reproducible offline.
- [5.6 Postgres Checkpointer and Store for Production](5.6-postgres-persistence/README.md) — Runs the reading-list assistant on PostgresSaver and PostgresStore against a real Postgres server: connection strings from the environment, setup(), and sharing state between two separate processes.

[Home](../README.md)

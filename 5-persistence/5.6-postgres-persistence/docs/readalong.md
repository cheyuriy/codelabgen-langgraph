# 5.6 Postgres Checkpointer and Store for Production — code walkthrough

This is the reading-list assistant from lesson 5.5, with both memories moved into a real Postgres server. The checkpointer is now `PostgresSaver` and the store is `PostgresStore` with the 5.5 embedding index. The parent process creates the tables. Four separate child processes then hold the conversations, and Monday's thread continues in a second process. At the end the parent, which never ran a conversation, reads everything back from the database and prunes old checkpoints. Run it with `./run.sh 5.6` from the course root. It starts the course Postgres from `docker-compose.yml` (image `pgvector/pgvector:pg17` on `localhost:13682`, URL in `POSTGRES_URL` in `.env`).
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 5.5

- [pyproject.toml](../pyproject.toml#L11-L13) adds `langgraph-checkpoint-postgres`, `psycopg[binary]` and `psycopg-pool`.
- [assistant.py](../src/l5_6_postgres_persistence/assistant.py) is copied from 5.5 unchanged. `MEMORY_INDEX` lives there and `build_graph` takes the checkpointer and store as arguments, so swapping the backends needs no change in this file.
- [`open_postgres`](../src/l5_6_postgres_persistence/__main__.py#L41-L75) is new. It replaces the two 5.5 lines that created `InMemorySaver()` and `InMemoryStore(index=MEMORY_INDEX)`.
- The 5.5 scripts moved into [`play_scene`](../src/l5_6_postgres_persistence/__main__.py#L104-L145). Monday's third message is now its own step, `monday-evening`, on the same thread.
- Each step runs in its own Python process: [`run_step` and `run_process`](../src/l5_6_postgres_persistence/__main__.py#L151-L177), dispatched by [`main`](../src/l5_6_postgres_persistence/__main__.py#L303-L308).
- [`demo`](../src/l5_6_postgres_persistence/__main__.py#L203-L299) calls `setup()` on both classes, lists the tables, and calls the new [`reset_demo`](../src/l5_6_postgres_persistence/__main__.py#L180-L200).
- The inspect and keys-versus-meaning sections now run in the parent after all the children. The new [checkpoint growth](../src/l5_6_postgres_persistence/__main__.py#L277-L300) section counts and prunes checkpoints.
- [test_postgres_persistence.py](../tests/test_postgres_persistence.py) is new and runs offline on in-memory stand-ins. 5.5's tests are not copied.

Unchanged: the whole of `assistant.py` (the fake embedding, `MEMORY_INDEX`, the nodes, `build_graph`) and the `chat` and `message_count` helpers. They are explained in the [5.5 walkthrough](../../5.5-semantic-memory-search/docs/readalong.md).

## [pyproject.toml](../pyproject.toml)

- [Line 11](../pyproject.toml#L11): the Postgres classes are a separate package, `langgraph-checkpoint-postgres`. They are not part of `langgraph`. Version 3.2.0 belongs with `langgraph-checkpoint` 4.x on [line 8](../pyproject.toml#L8). Keep the checkpoint packages pinned together.
- [Line 12](../pyproject.toml#L12): `psycopg` is the Postgres driver the classes use. The `[binary]` extra ships its own copy of `libpq`, the Postgres client library, so nothing needs to be installed on the machine.
- [Line 13](../pyproject.toml#L13): `psycopg-pool` provides `ConnectionPool`. The lesson code doesn't import it, but the comments in `open_postgres` and one experiment do, so it is pinned.
- `numpy` stays on [line 10](../pyproject.toml#L10). The tests use `InMemoryStore`, which computes cosine similarity with numpy, as in 5.5.

## [\_\_main\_\_.py](../src/l5_6_postgres_persistence/__main__.py)

The file runs in two roles. Started without arguments, it is the parent and runs `demo`. Started with a step name, it is a child and plays that one step. Both roles are the same module, so they share the constants on [lines 32-38](../src/l5_6_postgres_persistence/__main__.py#L32-L38). Nothing at the top of the file reads the environment or connects anywhere, so the tests can import it without a database.

### [`open_postgres`](../src/l5_6_postgres_persistence/__main__.py#L41-L75)

This is the heart of the lesson. Everything the graph remembers now goes through these two objects.

- `@contextmanager` turns the generator into a `with` block. The body up to `yield` runs when the block is entered, and the inner `with` closes both connections when the block ends. The graph therefore has to be built and used inside `with open_postgres() as (...)`. After the block its connections are closed.
- [Line 52](../src/l5_6_postgres_persistence/__main__.py#L52) reads `POSTGRES_URL` only when the block is entered. Without the variable you get a `KeyError` before any connection is attempted. The first test checks exactly this.
- [Line 68](../src/l5_6_postgres_persistence/__main__.py#L68): `PostgresSaver.from_conn_string` is itself a context manager. It opens one psycopg connection with `autocommit=True`, `prepare_threshold=0` and `row_factory=dict_row`, wraps it in a saver, and closes it at the end. `autocommit=True` makes every statement commit on its own, so the saver doesn't depend on you to commit. `dict_row` makes rows come back as dicts, which `demo` uses on line 226.
- [Line 73](../src/l5_6_postgres_persistence/__main__.py#L73): `PostgresStore.from_conn_string` does the same for the store and opens a second connection. `index=MEMORY_INDEX` is the same dict that 5.5 passed to `InMemoryStore`. `PostgresIndexConfig` extends the same `IndexConfig`, so it is accepted as is. The difference is that `dims` now matters: `setup()` creates a `vector(6)` column from it, and Postgres rejects any vector of another length.
- One connection per object is fine for a script that runs one conversation at a time. The comment on lines 58-66 describes the setup for a server: one `ConnectionPool` shared by both classes, opened with the same three connection settings. Without `autocommit=True`, `setup()` fails on a new database, because it creates indexes with `CREATE INDEX CONCURRENTLY`, which Postgres refuses inside a transaction.

### [`chat` and `message_count`](../src/l5_6_postgres_persistence/__main__.py#L81-L97)

The same as in 5.5. `message_count` calls `graph.get_state`, which now loads the latest checkpoint of the thread from Postgres.

### [`play_scene`](../src/l5_6_postgres_persistence/__main__.py#L104-L145)

One `match` case per step. The function receives a ready graph and doesn't know which backend is behind it. That is why the tests can run the same scenes on `InMemorySaver` and `InMemoryStore`.

- [`monday`](../src/l5_6_postgres_persistence/__main__.py#L112-L117) prints how many messages the thread already has (0 after the reset), then Ada's two taste sentences. Each `invoke` writes checkpoints to Postgres, and `remember` writes her genres to the store.
- [`monday-evening`](../src/l5_6_postgres_persistence/__main__.py#L118-L124) runs in a different process with a newly built graph. It uses the same `thread_id`, `"monday"`, so the saver loads the latest checkpoint for that thread: 4 messages. The new turn is appended to them. The reply lists both books because the genres came back from the store.
- [`tuesday`](../src/l5_6_postgres_persistence/__main__.py#L125-L137) starts a new thread, so its history is empty, while `monday` now holds 6 messages. Ada's memories are in the store under her namespace, so the scored picks work as in 5.5, only in a third process.
- [`bob`](../src/l5_6_postgres_persistence/__main__.py#L138-L143) is the 5.5 Bob script on thread `bob-1`.
- [Lines 144-145](../src/l5_6_postgres_persistence/__main__.py#L144-L145): an unknown step raises `ValueError` instead of doing nothing. A typo in a step name would otherwise make a child print nothing and exit successfully.

### [`run_step` and `run_process`](../src/l5_6_postgres_persistence/__main__.py#L151-L177)

- [`run_step`](../src/l5_6_postgres_persistence/__main__.py#L152-L156) is what a child does: open Postgres, build the graph, play one scene, close the connections.
- [`run_process`](../src/l5_6_postgres_persistence/__main__.py#L159-L174) is what the parent does for each step. [Line 174](../src/l5_6_postgres_persistence/__main__.py#L174) starts `python -m l5_6_postgres_persistence <step>` with the same interpreter (`sys.executable`, so the same virtual environment) and waits for it to finish. The child gets a copy of the parent's environment, `POSTGRES_URL` included. No Python objects are passed. The child has only the URL, the step name, and through the step the `thread_id`.
- `flush=True` on [line 166](../src/l5_6_postgres_persistence/__main__.py#L166) matters because the child writes to the same terminal. Without it, the parent's header could still sit in its output buffer when the child's lines appear, and the output would be out of order.

### [`reset_demo`](../src/l5_6_postgres_persistence/__main__.py#L180-L200)

Postgres keeps the data after the program exits. That is the point of the lesson, but it means a second run would continue the first run's threads, and the output would change. `reset_demo` removes only this demo's data.

- [Line 192](../src/l5_6_postgres_persistence/__main__.py#L192): `delete_thread` deletes all rows for that `thread_id` from `checkpoints`, `checkpoint_blobs` and `checkpoint_writes`. A thread that doesn't exist is not an error, so the reset also works on the first run.
- [Line 195](../src/l5_6_postgres_persistence/__main__.py#L195) lists the user's memories with `search` and no query. `limit=100` raises the default limit of 10, so a larger demo would not leave items behind.
- [Line 197](../src/l5_6_postgres_persistence/__main__.py#L197) deletes each item by its own namespace and key. The row in `store_vectors` goes with it, because the table's foreign key to `store` is declared `ON DELETE CASCADE`.
- The parameters are typed as `BaseCheckpointSaver` and `BaseStore`, so the tests can pass the in-memory classes.

### [`demo`](../src/l5_6_postgres_persistence/__main__.py#L203-L299)

The parent's run in three parts: prepare the database, run the children, read back.

**Setup** ([lines 206-229](../src/l5_6_postgres_persistence/__main__.py#L206-L229)):

- [Line 215](../src/l5_6_postgres_persistence/__main__.py#L215) and [line 218](../src/l5_6_postgres_persistence/__main__.py#L218) run the migrations. Each class keeps a table of the migration numbers it has already applied and runs only the missing ones, so calling `setup()` on every run costs almost nothing. On a new database the saver creates its four tables, and the store creates `store`, `store_migrations`, `vector_migrations` and `store_vectors`. Because of the index, the store also enables the `vector` extension. That is why the course uses the `pgvector/pgvector` image: on plain `postgres:17` this line fails with "extension "vector" is not available". If you skip `setup()` on a new database, the first query fails because the tables don't exist. Here that would be `delete_thread` in `reset_demo`.
- [Lines 221-226](../src/l5_6_postgres_persistence/__main__.py#L221-L226) run plain SQL on the saver's own connection, `checkpointer.conn`, to show which tables now exist. `r["tablename"]` works because of `dict_row`.
- [Line 227](../src/l5_6_postgres_persistence/__main__.py#L227) runs the reset. The `with` block ends on line 229, so the parent's connections are closed before any child starts.

**Children** ([lines 232-234](../src/l5_6_postgres_persistence/__main__.py#L232-L234)): one process per step, one after another. Each waits for the previous one to finish, so the order of the conversations is fixed.

**Reading back**: [line 236](../src/l5_6_postgres_persistence/__main__.py#L236) opens new connections, and [line 238](../src/l5_6_postgres_persistence/__main__.py#L238) builds a graph that has never been invoked. It is used only for `message_count`, which reads state from the saver.

- [Inspect the store](../src/l5_6_postgres_persistence/__main__.py#L240-L256): the same calls as in 5.5, now answered by SQL. The values print with their keys as `note`, `genre`, `stance`, not in the order `remember` wrote them. The store keeps values in a `jsonb` column, and `jsonb` does not keep the original key order. The dict is equal, only the printed order differs. `messages per thread` shows 6, 8 and 6, all written by other processes.
- [Keys versus meaning](../src/l5_6_postgres_persistence/__main__.py#L259-L273): [line 268](../src/l5_6_postgres_persistence/__main__.py#L268) embeds the query in Python with `embed_texts` and sends the vector to Postgres. pgvector computes the cosine distance, and the store reports `1 - distance` as the score. The numbers are the same as with `InMemoryStore`. `setup()` also created an HNSW index on the vectors, but the 3.2.0 source notes that the current search query cannot use it, so every vector is compared and the results are exact.
- [Checkpoint growth](../src/l5_6_postgres_persistence/__main__.py#L277-L300):
  - [`checkpoint_count`](../src/l5_6_postgres_persistence/__main__.py#L278-L280) counts what `checkpointer.list` returns for one thread: every saved checkpoint, newest first.
  - [Line 285](../src/l5_6_postgres_persistence/__main__.py#L285) prints 9, 12 and 9: three checkpoints per turn in this graph, times 3, 4 and 3 turns.
  - [Line 295](../src/l5_6_postgres_persistence/__main__.py#L295): `prune` takes a list of thread ids. A bare string raises `TypeError`. `keep_latest` deletes every checkpoint of those threads except the newest. `bob-1` is not in the list and keeps its 9.
  - [Lines 298-299](../src/l5_6_postgres_persistence/__main__.py#L298-L299) show that no messages were lost. The newest checkpoint holds the whole current state, while the older ones only held the history. What is gone is the ability to look at or go back to earlier steps.

### [`main`](../src/l5_6_postgres_persistence/__main__.py#L303-L308)

`python -m l5_6_postgres_persistence` with one argument is a child running that step. Without arguments it is the parent running the whole demo. You can start a child yourself after a run, for example with step `monday-evening`. It continues the same thread, because the thread lives in the database.

## [test_postgres_persistence.py](../tests/test_postgres_persistence.py)

`verify` runs the tests before it starts Postgres, so they never connect to a database. They use `InMemorySaver` and `InMemoryStore` as stand-ins. That works because `play_scene` and `reset_demo` only use what every saver and store provides.

- [`play_all`](../tests/test_postgres_persistence.py#L58-L61) builds a new graph for each step but shares one saver and one store. That is how the live run behaves: a new graph in every process, the same database behind all of them.
- [`test_no_database_at_import_and_url_read_lazily`](../tests/test_postgres_persistence.py#L64-L74): [line 68](../tests/test_postgres_persistence.py#L68) reloads the module without `POSTGRES_URL`, which proves that importing it needs no environment. Entering `open_postgres()` then raises `KeyError` from line 52 of `__main__.py`, before any connection. Lines 73-74 check that the embedding has length 6, the size of the `vector` column.
- [`test_state_lives_in_the_backend`](../tests/test_postgres_persistence.py#L77-L82): the conversation lines must match the live run exactly, including "thread monday starts with 4 messages". The graph is new each time, so the history can only come from the shared saver.
- [`test_a_process_with_its_own_backend_sees_nothing`](../tests/test_postgres_persistence.py#L85-L91) is the opposite case: `monday-evening` on new, empty in-memory backends finds 0 messages and no genres. A second process with an in-memory backend would see exactly this. Postgres removes this problem.
- [`test_reset_demo_deletes_only_the_demo_data`](../tests/test_postgres_persistence.py#L94-L113) adds a thread and a memory that are not part of the demo, resets, and checks that only the demo's threads and memories are gone. [Line 109](../tests/test_postgres_persistence.py#L109) checks `search` instead of `list_namespaces`, because `InMemoryStore` keeps listing a namespace after all its items are deleted. [Line 113](../tests/test_postgres_persistence.py#L113) shows that a second reset is harmless.
- [`test_play_scene_rejects_unknown_steps`](../tests/test_postgres_persistence.py#L116-L120): the `ValueError` from the default case.

The tests can't cover what only a real server does: `setup()`, the `vector(6)` column, the `jsonb` key order and `prune`. The live run checks those.

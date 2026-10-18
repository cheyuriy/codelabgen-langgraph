# 5.6 Postgres Checkpointer and Store for Production

## The problem

Module 5 has given the reading-list assistant two kinds of memory, one lesson at a time:

- [Lesson 5.1](../../5.1-checkpointers-and-threads/docs/notes.md) added a [checkpointer](../../../GLOSSARY.md#checkpointer). It saves each [thread_id](../../../GLOSSARY.md#thread_id)'s state as [checkpoints](../../../GLOSSARY.md#checkpoint), so a conversation continues where it stopped. [InMemorySaver](../../../GLOSSARY.md#inmemorysaver) kept them in a dict.
- [Lesson 5.2](../../5.2-sqlite-checkpointer/docs/notes.md) moved the checkpoints into a file with [SqliteSaver](../../../GLOSSARY.md#sqlitesaver). A second process could then continue a thread, and a crash left the finished steps on disk.
- [Lesson 5.3](../../5.3-message-history/docs/notes.md) kept the message history from growing without limit.
- [Lesson 5.4](../../5.4-long-term-memory-store/docs/notes.md) added [long-term memory](../../../GLOSSARY.md#long-term-memory): an [InMemoryStore](../../../GLOSSARY.md#inmemorystore) holding each user's genres across threads.
- [Lesson 5.5](../../5.5-semantic-memory-search/docs/notes.md) gave that store an embedding index, so "Something with a spaceship" finds the sci-fi memory.

Two gaps are left. First, the store is still in memory. When the process ends, every genre Ada told the assistant is gone, which is exactly the weakness 5.2 fixed for checkpoints. Second, a SQLite file is not enough for a real service. 5.2 named its limits: the file lives on one machine, and SQLite lets only one connection write at a time. A web service usually runs several worker processes, often on several machines, and any of them may get the next message of any conversation. They all need to reach the same memory at the same time.

The usual answer is a database server that every process connects to over the network. LangGraph ships a checkpointer and a store for Postgres. This lesson moves both of the assistant's memories into a Postgres server and proves that only the database connects the processes: four separate Python processes hold the conversations, and a parent that never ran one reads everything back.

## The concept

### Two classes, one package

[PostgresSaver](../../../GLOSSARY.md#postgressaver) is a checkpointer and [PostgresStore](../../../GLOSSARY.md#postgresstore) is a store. Both live in the `langgraph-checkpoint-postgres` package (3.2.0 here), which `langgraph` does not install, and both talk to Postgres through the `psycopg` driver (version 3). The official checkpointers guide calls the Postgres saver "Ideal for using in production", and the stores guide recommends a persistent store such as `PostgresStore` for production, with `InMemoryStore` for development and testing.

They implement the same interfaces as the classes you already know: `PostgresSaver` is a [BaseCheckpointSaver](../../../GLOSSARY.md#basecheckpointsaver) like `InMemorySaver` and `SqliteSaver`, and `PostgresStore` is a [BaseStore](../../../GLOSSARY.md#basestore) like `InMemoryStore`. The graph only ever calls those interfaces, so the nodes, the routing, the namespaces and the search code from 5.4 and 5.5 stay exactly as they were. What changes is where the data goes, and three things you now have to look after: connections, the database schema and the size of the data.

### Opening them: from_conn_string

Like `SqliteSaver` in 5.2, both classes have a [from_conn_string](../../../GLOSSARY.md#from_conn_string) classmethod that is a context manager. Instead of a file path it takes a Postgres connection string, a URL of the form `postgresql://user:password@host:port/database`. On entry it opens **one** psycopg connection with three settings, and when the block ends it closes it:

- `autocommit=True`. Every SQL statement is committed on its own, so no transaction is ever left open. This [autocommit](../../../GLOSSARY.md#autocommit) mode is not optional, as the next section shows.
- `row_factory=dict_row`. Rows come back as dicts, so columns are read by name (`row["tablename"]`) instead of by position. In 3.2.0 the classes' own cursors ask for dict rows anyway, but the package README requires this setting for connections you open yourself, and your own queries on the same connection, like the lesson's table listing, rely on it.
- `prepare_threshold=0`, a psycopg setting for server-side prepared statements.

`PostgresStore.from_conn_string` also takes `index=` (the same index config as `InMemoryStore`) and `pool_config=`, which makes it open a pool of connections instead of one (more on pools below).

The consequences are the same as with SQLite: use the graph inside the `with` block, because the connection is closed afterwards, and keep the block open for as long as the application needs the graph. One difference matters, though. `SqliteSaver` needed `check_same_thread=False` because of a SQLite rule. Postgres has no such rule. A psycopg connection still runs only one query at a time, though, and `PostgresSaver` guards its database calls with a lock, much as `SqliteSaver` did.

### setup() is a schema migration

`SqliteSaver` creates its tables itself the first time it touches the file. The Postgres classes do not. Their tables come from an explicit call, `setup()`, and the docstrings of both classes say it "MUST be called directly by the user the first time". Forget it on a new database, and the first query fails with `relation "checkpoints" does not exist`.

`setup()` is a small [schema migration](../../../GLOSSARY.md#schema-migration) runner. Each class carries an ordered list of SQL changes: create a table, add a column, build an index. It records the numbers of the changes it has already applied in its own table, and on every call it applies only the ones the database has not seen yet. Calling `setup()` again is therefore harmless and quick. It also means that a newer version of the package can bring new migrations, and the next `setup()` applies them to the existing tables.

These are the tables `setup()` creates in this lesson:

| Class | Table | Holds |
|---|---|---|
| `PostgresSaver` | `checkpoint_migrations` | the numbers of the applied migrations |
| | `checkpoints` | one row per checkpoint: thread, id, parent, metadata |
| | `checkpoint_blobs` | the channel values (the state itself), one row per channel version |
| | `checkpoint_writes` | the [pending writes](../../../GLOSSARY.md#pending-writes) of single tasks |
| `PostgresStore` | `store_migrations` | the numbers of the applied migrations |
| | `store` | one row per item: namespace, key, `value` as `jsonb`, timestamps |
| `PostgresStore` with `index=` | `vector_migrations` | the numbers of the applied vector migrations |
| | `store_vectors` | one embedding per item and embedded field, in a `vector(dims)` column |

Several migrations build indexes with `CREATE INDEX CONCURRENTLY`, which Postgres refuses to run inside a transaction. That is the reason for `autocommit=True`: a connection without it opens a transaction implicitly, and `setup()` fails on a new database.

The official memory guide recommends running migrations "as a dedicated deployment step", or as part of server startup. Treat `setup()` that way: once per deploy, before the service takes traffic, not on every request.

### The index lives in a pgvector column

5.5's `MEMORY_INDEX` is passed to `PostgresStore` unchanged. Its type, `PostgresIndexConfig`, extends the [IndexConfig](../../../GLOSSARY.md#indexconfig) that `InMemoryStore` takes, so `dims`, `embed` and `fields` mean the same as before. Two things are new.

**The vectors need [pgvector](../../../GLOSSARY.md#pgvector).** pgvector is a Postgres extension that adds a `vector` column type and distance operators. When the store has an index, `setup()` runs `CREATE EXTENSION vector` (only if the extension is not enabled yet) and creates `store_vectors` with an `embedding vector(dims)` column. The extension has to be installed in the database server for that to work. The stock `postgres` Docker image does not include it, and `store.setup()` fails there with `extension "vector" is not available`. That is why the course's `docker-compose.yml` runs `pgvector/pgvector:pg17`, the official Postgres image with pgvector added. A `PostgresStore` without `index=` needs no extension at all, and, as in 5.5, it ignores `query=` and returns `score=None`.

**`dims` is now enforced.** `InMemoryStore` never looked at `dims`. Here it becomes the length of a database column, fixed when `setup()` runs, and Postgres rejects any vector of another length.

The search itself moves into the database. `search(namespace, query=...)` still embeds the query in Python with your `embed` function. Then it sends the vector to Postgres, which computes the cosine distance with pgvector's `<=>` operator, and the store reports `1 - distance` as the score. That is the [cosine similarity](../../../GLOSSARY.md#cosine-similarity) from 5.5, so the scores match `InMemoryStore`'s. `filter=` becomes a `jsonb` condition in the same SQL query, so it still removes items before they are ranked.

### The thread_id is the only key

5.2 made the point for a file, and it holds for a server too: a process that wants to continue a conversation knows nothing about it except the database URL and the thread_id. Use the same thread_id and the saver loads that thread's latest checkpoint. Use a new one and the conversation starts empty, even though the old one is still in the database. `PostgresSaver` stores the thread_id in `TEXT` columns and converts it with `str()` first, as `SqliteSaver` does.

## How it works

The demo runs every step of the story in its own Python process. The diagram shows that the only thing they share is the Postgres server:

```mermaid
flowchart LR
    P["parent: demo()"] -->|"setup(), reset_demo()"| DB[("Postgres")]
    M["process monday"] -->|"thread monday, Ada's genres"| DB
    DB -->|"4 messages"| E["process monday-evening"]
    E -->|"thread monday"| DB
    DB -->|"Ada's genres"| T["process tuesday"]
    T -->|"thread tuesday"| DB
    B["process bob"] -->|"thread bob-1, Bob's genres"| DB
    DB -->|"read back, prune()"| R["parent again"]
```

1. The parent opens both classes, runs both `setup()` calls, lists the tables, and deletes the data of earlier runs. Then it closes its connections.
2. It starts four children one after another with `python -m l5_6_postgres_persistence <step>`. Each child opens its own two connections, builds a new graph and plays one step. The checkpointer writes the thread's checkpoints, and the `remember` node writes genres to the store.
3. `monday-evening` is the key moment. It is a brand-new process with a brand-new graph, and it uses the thread_id `"monday"`. The saver loads that thread's latest checkpoint from Postgres, 4 messages, and [add_messages](../../../GLOSSARY.md#add_messages) appends the new turn to them.
4. The parent opens new connections, reads the store and the threads back, and prunes old checkpoints.

Nothing in any process's memory survives into the next one. If a child got its data from anywhere but Postgres, the output would show it.

## In our example

The example extends the reading-list assistant of [lesson 5.5](../../5.5-semantic-memory-search/docs/notes.md). [assistant.py](../src/l5_6_postgres_persistence/assistant.py) is copied without a single change: 5.4 made `build_graph` take the checkpointer and the store as parameters, and 5.5 kept `MEMORY_INDEX` in that file, both so that this lesson would only need a new [\_\_main\_\_.py](../src/l5_6_postgres_persistence/__main__.py). The graph is still 5.5's: `__start__` routes to `remember` or `recommend`, and both end the run. The [code walkthrough](readalong.md) goes through every line, starting with [what changed since 5.5](readalong.md#what-changed-since-lesson-55). Here we map the concepts onto the code.

### Connecting: open_postgres

`open_postgres` is the whole switch from memory to Postgres. It replaces 5.5's two lines, `InMemorySaver()` and `InMemoryStore(index=MEMORY_INDEX)`:

<!-- snippet: src/l5_6_postgres_persistence/__main__.py#connect -->
```python
@contextmanager
def open_postgres() -> Iterator[tuple[PostgresSaver, PostgresStore]]:
    """Open the Postgres checkpointer and store, and close them when the block ends.

    This replaces the two lines of 5.5, `checkpointer = InMemorySaver()` and
    `store = InMemoryStore(index=MEMORY_INDEX)`. build_graph and the nodes do
    not change at all.
    """
    # The URL holds a password, so it comes from the environment and is never
    # hard-coded. It is read here, when the function runs, not at import time.
    url = os.environ["POSTGRES_URL"]
    # Each from_conn_string is a @contextmanager that opens ONE psycopg
    # connection (autocommit=True, prepare_threshold=0, row_factory=dict_row)
    # and closes it when the block ends, so the graph must be used inside the
    # block. Here that means two connections, one for each class.
    #
    # A web server that handles many requests at once shares a
    # psycopg_pool.ConnectionPool instead: PostgresSaver(pool) and
    # PostgresStore(pool, index=...) both accept one. The pool must open its
    # connections with kwargs={"autocommit": True, "prepare_threshold": 0,
    # "row_factory": dict_row}. Alternatively,
    # PostgresStore.from_conn_string(url, index=..., pool_config={"min_size": 1,
    # "max_size": 10}) builds such a pool for the store. autocommit matters:
    # setup() runs CREATE INDEX CONCURRENTLY, which Postgres refuses inside a
    # transaction.
    with (
        PostgresSaver.from_conn_string(url) as checkpointer,
        # The same MEMORY_INDEX as in 5.5. Its dims, which InMemoryStore
        # ignored, now sizes the vector(6) column that setup() creates, and the
        # server needs the pgvector extension. A PostgresStore without index=
        # needs no pgvector and ignores query=, as in 5.5.
        PostgresStore.from_conn_string(url, index=MEMORY_INDEX) as store,
    ):
        yield checkpointer, store
```
<!-- /snippet -->

- The URL comes from the `POSTGRES_URL` environment variable, read when the block is entered, not when the module is imported. It contains a password, so it never appears in the code. `./run.sh 5.6` loads it from the course `.env`.
- Two `from_conn_string` blocks mean two connections, one per class. For a script that runs one conversation at a time that is fine. The long comment describes what a server does instead, with a shared pool; the [operational concerns](#running-it-for-real-the-operational-concerns) below come back to it.
- `index=MEMORY_INDEX` is 5.5's dict. Its `dims` (6) now sizes the `vector(6)` column.
- `open_postgres` is itself a context manager, so callers write `with open_postgres() as (checkpointer, store):` and must use the graph inside that block. The walkthrough explains it in [`open_postgres`](readalong.md#open_postgres).

### Creating the tables: setup()

The parent runs the migrations once, before any child starts:

<!-- snippet: src/l5_6_postgres_persistence/__main__.py#setup_tables -->
```python
print("== setup (once, in the parent) ==")
# Unlike SqliteSaver in 5.2, which sets itself up, the Postgres classes
# need setup() called explicitly the first time: their docstrings say
# it "MUST be called directly by the user the first time". setup() is
# a migration. Each class records the migrations it has applied
# (checkpoint_migrations, store_migrations, vector_migrations) and runs
# only new ones, so calling it again is harmless. In production it
# runs once per deploy, not per request.
checkpointer.setup()
# The vector migrations run CREATE EXTENSION vector (if it is not there
# yet) and create store_vectors with an embedding vector(dims) column.
store.setup()
# Rows are dicts because of row_factory=dict_row. The LIKE filter lists
# only LangGraph's tables.
rows = checkpointer.conn.execute(
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    " AND (tablename LIKE 'checkpoint%' OR tablename LIKE 'store%'"
    " OR tablename LIKE 'vector%') ORDER BY tablename"
).fetchall()
print("  tables: " + ", ".join(r["tablename"] for r in rows))
reset_demo(checkpointer, store)
print("  old demo threads and memories removed")
```
<!-- /snippet -->

The query on `pg_tables` is plain SQL on the saver's own connection, `checkpointer.conn`, only to show what `setup()` created. `r["tablename"]` works because of `dict_row`. On the course database the tables exist after the first run, so later runs apply no migrations, and the same eight names are listed every time.

### One step per process

Each child runs `run_step`, and the parent starts each child with `run_process`:

<!-- snippet: src/l5_6_postgres_persistence/__main__.py#child_process -->
```python
def run_step(step: str) -> None:
    """Run one step in this process, on Postgres (what each child process does)."""
    with open_postgres() as (checkpointer, store):
        graph = build_graph(checkpointer, store)
        play_scene(step, graph)


def run_process(step: str) -> None:
    """Run one step in a brand-new Python process and wait for it to finish.

    Nothing is shared with the parent except the database: the child inherits
    POSTGRES_URL from the environment and finds the threads and memories there.
    """
    # Flush the header first so it prints before the child's own output.
    print(f"== process: {step} ==", flush=True)
    # check=True makes a failing child stop the demo with CalledProcessError;
    # the child's traceback appears on stderr.
    #
    # The thread_id is the only key to a conversation. Any process that knows
    # the URL and the thread_id can continue it, so a real app stores the
    # thread id with the user's session and never makes a fresh uuid4 per
    # process. PostgresSaver keeps it in a TEXT column (str(thread_id)).
    subprocess.run([sys.executable, "-m", PACKAGE, step], check=True)
```
<!-- /snippet -->

`sys.executable` starts the same interpreter, so the child has the same virtual environment, and it inherits the parent's environment variables, `POSTGRES_URL` included. No Python object crosses from parent to child. The child has the URL and a step name, and the step decides the thread_id.

The steps themselves are 5.5's scripts, moved into `play_scene`. The only change is that Monday's third message became its own step on the same thread:

<!-- snippet: src/l5_6_postgres_persistence/__main__.py#monday_evening -->
```python
# The same thread_id in a different process. The 4 messages come
# from Postgres, and add_messages appends the new turn to them.
print(f"  thread monday starts with {message_count(graph, 'monday')} messages")
chat(graph, "monday", "ada", "Any book for tonight?")
```
<!-- /snippet -->

`play_scene` receives a ready graph and knows nothing about Postgres. That is why the tests can play the same scenes on `InMemorySaver` and `InMemoryStore` without a database: one saver and one store shared by a new graph per step behave like Postgres shared by a new process per step. The walkthrough covers this in [`play_scene`](readalong.md#play_scene) and [`run_step` and `run_process`](readalong.md#run_step-and-run_process).

### Starting clean: reset_demo

Postgres keeps everything after the program exits. That is the point of the lesson, but it means a second run would continue the first run's threads, and the output would change (first experiment). `reset_demo` removes this demo's data, and only that:

<!-- snippet: src/l5_6_postgres_persistence/__main__.py#reset_demo -->
```python
def reset_demo(checkpointer: BaseCheckpointSaver, store: BaseStore) -> None:
    """Delete this demo's threads and memories, so every run starts clean.

    Postgres outlives the process. Without this, a second run would continue
    the previous run's threads and memories, and the output would change.
    A real app never wipes data like this: delete_thread and store.delete
    belong in "delete my data" requests. The type hints are the base classes,
    so the same function works on any backend (the tests use in-memory ones).
    """
    for thread_id in THREADS:
        # Removes only this thread's checkpoints, blobs and pending writes.
        checkpointer.delete_thread(thread_id)
    for user_id in USERS:
        ns = genres_namespace(user_id)
        for item in store.search(ns, limit=100):
            # The item's vector in store_vectors goes with it (ON DELETE CASCADE).
            store.delete(item.namespace, item.key)
```
<!-- /snippet -->

`delete_thread` deletes the thread's rows from `checkpoints`, `checkpoint_blobs` and `checkpoint_writes`. A thread that does not exist is not an error. `store.delete` removes one item. Its embedding in `store_vectors` goes with it, because that table's foreign key to `store` is declared `ON DELETE CASCADE`. A real application never wipes data like this, but it needs the same two calls when a user asks to delete their data.

### Keeping growth in check: prune

Back in the parent, after the store has been read back, the last section counts checkpoints and prunes them:

<!-- snippet: src/l5_6_postgres_persistence/__main__.py#checkpoint_growth -->
```python
def checkpoint_count(checkpointer: BaseCheckpointSaver, thread_id: str) -> int:
    """Return how many checkpoints the saver holds for a thread."""
    return len(list(checkpointer.list({"configurable": {"thread_id": thread_id}})))

print("== Checkpoint growth ==")
# Every step of every invoke writes a checkpoint (3 per turn in this
# graph), so a long-lived thread grows without limit.
counts = ", ".join(f"{t}={checkpoint_count(checkpointer, t)}" for t in THREADS)
print(f"  checkpoints per thread: {counts}")
# The latest checkpoint alone holds the whole current state. After
# keep_latest the threads still have all their messages, but the older
# checkpoints (the history) are gone. strategy="delete" removes whole
# threads. prune takes a list of thread ids and is meant for a
# maintenance job over old threads. bob-1 is left alone for contrast.
# To write fewer checkpoints in the first place, invoke with
# durability="exit" (lesson 5.2). The deprecated ShallowPostgresSaver
# points there too.
checkpointer.prune(["monday", "tuesday"], strategy="keep_latest")
counts = ", ".join(f"{t}={checkpoint_count(checkpointer, t)}" for t in THREADS)
print(f"  after prune keep_latest: {counts}")
counts = ", ".join(f"{t}={message_count(graph, t)}" for t in THREADS)
print(f"  messages per thread: {counts}")
```
<!-- /snippet -->

`checkpointer.list(config)` returns every saved checkpoint of a thread, newest first. `prune` takes a list of thread ids. With `strategy="keep_latest"` it keeps only the newest checkpoint of each thread. `bob-1` is left out of the list on purpose, for contrast.

## Run it

From the course root, run `./run.sh 5.6`. It starts the Postgres service from `docker-compose.yml` if it is not running, loads `POSTGRES_URL` from `.env`, and runs the lesson. This is the output of the verified run:

```text
== setup (once, in the parent) ==
  tables: checkpoint_blobs, checkpoint_migrations, checkpoint_writes, checkpoints, store, store_migrations, store_vectors, vector_migrations
  old demo threads and memories removed

== process: monday ==
  thread monday starts with 0 messages
  ada> I love sci-fi: robots and distant planets.
  bot> Noted: sci-fi (like).
  ada> I like mystery too, a detective in ancient Rome.
  bot> Noted: mystery (like).

== process: monday-evening ==
  thread monday starts with 4 messages
  ada> Any book for tonight?
  bot> Try: The Hound of the Baskervilles (mystery); Dune (sci-fi).

== process: tuesday ==
  thread tuesday starts with 0 messages; thread monday holds 6
  ada> Something with a spaceship, please.
  bot> Try: Dune (sci-fi, score 0.89).
  ada> I am in the mood for a whodunit.
  bot> Try: The Hound of the Baskervilles (mystery, score 0.71).
  ada> Please skip mystery for now.
  bot> Noted: mystery (like -> avoid).
  ada> I am in the mood for a whodunit.
  bot> Try: Dune (sci-fi).

== process: bob ==
  bob> Recommend something.
  bot> Tell me a genre you like and I will pick a book.
  bob> I love fantasy: dragons, wizards and an old king.
  bot> Noted: fantasy (like).
  bob> Anything with a wizard?
  bot> Try: The Hobbit (fantasy, score 0.95).

== back in the parent: what Postgres holds ==
  namespaces: [('ada', 'genres'), ('bob', 'genres')]
  ('ada', 'genres') 'mystery': {'note': 'Please skip mystery for now.', 'genre': 'mystery', 'stance': 'avoid'}
  ('ada', 'genres') 'sci-fi': {'note': 'I love sci-fi: robots and distant planets.', 'genre': 'sci-fi', 'stance': 'like'}
  ('bob', 'genres') 'fantasy': {'note': 'I love fantasy: dragons, wizards and an old king.', 'genre': 'fantasy', 'stance': 'like'}
  get(('ada', 'genres'), 'sci-fi').value = {'note': 'I love sci-fi: robots and distant planets.', 'genre': 'sci-fi', 'stance': 'like'}
  get(('ada', 'genres'), 'fantasy') = None
  messages per thread: monday=6, tuesday=8, bob-1=6

== Keys versus meaning ==
  get(('ada', 'genres'), 'space') = None
  search(('ada', 'genres'), query='space robots'): sci-fi=0.95, mystery=0.00

== Checkpoint growth ==
  checkpoints per thread: monday=9, tuesday=12, bob-1=9
  after prune keep_latest: monday=1, tuesday=1, bob-1=9
  messages per thread: monday=6, tuesday=8, bob-1=6
```

The assistant is rule-based and the embedding is a fixed function, and `reset_demo` clears the old data first, so every run prints exactly this. What to notice:

- **Eight tables, from two `setup()` calls.** Four belong to the saver, four to the store. `store_vectors` and `vector_migrations` exist only because the store has an index.
- **A new process continues the thread.** `monday-evening` starts with 4 messages, which Monday's process wrote. Its reply lists both books, because Ada's genres came out of the store in yet another process.
- **The conversations are 5.5's.** Every reply and every score (0.89, 0.71, 0.95) is the same as with `InMemoryStore`, now computed by pgvector inside Postgres. Compare with the [5.5 output](../../5.5-semantic-memory-search/docs/notes.md#run-it).
- **The parent never chatted, yet it sees everything.** The namespaces, the items and `messages per thread: monday=6, tuesday=8, bob-1=6` were all written by other processes.
- **The values print in a different key order.** 5.5 printed `{'genre': ..., 'stance': ..., 'note': ...}`. Postgres prints `note` first. The store keeps values in a `jsonb` column, and `jsonb` does not keep the order of object keys. The dicts are equal; only the printed order differs.
- **Checkpoints grow by three per turn.** Every turn writes an input checkpoint, one after the input is applied, and one after the node runs: 3, 4 and 3 turns give 9, 12 and 9.
- **Pruning loses no messages.** After `keep_latest`, `monday` and `tuesday` have one checkpoint each and still all their messages. The newest checkpoint holds the whole current state. What is gone is the history of earlier steps.

## Running it for real: the operational concerns

The demo runs one conversation at a time on a database it owns. A real service has many users at once, deploys, and data that only grows. Three concerns come with that.

### Connections

`from_conn_string` gives each object one connection. One connection runs one query at a time, and if it breaks (the server restarts, the network drops), that object stays broken until you open a new one. A web server that serves many requests at once shares a [connection pool](../../../GLOSSARY.md#connectionpool) instead: a `psycopg_pool.ConnectionPool` keeps several open connections, lends one to each operation, and replaces connections that broke. Both classes accept a pool where they accept a connection:

```python
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

with ConnectionPool(
    url,
    max_size=10,
    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
) as pool:
    checkpointer = PostgresSaver(pool)
    store = PostgresStore(pool, index=MEMORY_INDEX)
```

The `kwargs` are the three settings `from_conn_string` uses. A pool hands them to every connection it opens, and it does not add them for you. Leave out `autocommit=True`, and `setup()` fails on a new database. On a database that is already migrated, the same pool works, so the mistake can hide until the next fresh deploy (fourth experiment). `PostgresStore.from_conn_string(url, index=..., pool_config={"max_size": 10})` builds such a pool for the store, with the right settings.

The `checkpointer.conn` attribute is whatever you passed in. With a pool it is the pool, not a connection, so code like the lesson's table listing (`checkpointer.conn.execute(...)`) has to borrow a connection with `pool.connection()` first.

The production toolkit listed under further reading does the same in async code: one pool per class with `autocommit` and `dict_row`, and `setup()` at startup. The async classes (`AsyncPostgresSaver`, `AsyncPostgresStore`) are not covered in this course.

### Thread ids

The thread_id is the only key to a conversation, so where it comes from matters more than how it looks. Store it with the user's session, a chat record or a cookie, and send it with every request. A fresh `uuid4()` per process or per request silently starts a new conversation each time, and the old one stays in the database with nothing pointing to it. The `TEXT` columns set no length limit, but readable, stable ids are easier to find when you inspect or delete a user's threads.

### Checkpoint growth

Every step of every run writes a checkpoint, and each holds the full state, so threads only grow. The persistence guide lists this under troubleshooting and suggests pruning or a retention policy, for example a scheduled job. You have two levers:

- **Write fewer checkpoints.** `graph.invoke(..., durability="exit")`, one of the [durability modes](../../../GLOSSARY.md#durability-mode) from 5.2, writes one checkpoint per run instead of one per step. On this graph that is 1 per turn instead of 3. The price, as 5.2 showed, is that a crash in the middle of a run leaves nothing of that run.
- **Delete old ones.** `prune(thread_ids, strategy="keep_latest")` keeps each thread's newest checkpoint and removes the rest. `strategy="delete"` removes whole threads, and `delete_thread` removes one. Run them from a maintenance job, for threads you have chosen, for example those idle for a month.

Both levers take away history: the earlier steps that time travel (lesson 6.5) would go back to. Keep it where you need it.

> [!NOTE]
> `ShallowPostgresSaver`, in the same package, used to be the answer to growth: it kept only the latest checkpoint of each thread. It is deprecated since 2.0.20, and constructing it warns you to use `PostgresSaver` with `durability="exit"` instead. Don't use it in new code.

### Migrations and the embedding size

`setup()` belongs in your deploy, and so do changes to the index. `dims` is fixed once the vector migration has run, and a later `setup()` does not resize the column: it sees the migration as applied and does nothing. Switching to an embedding model with a different vector length (fifth experiment), or even to another model with the same length, means embedding every stored item again into a new column or table. Plan it like any other data migration.

## Details and edge cases

**Pruning works per thread, inside a transaction.** `keep_latest` prunes each thread in its own transaction, on one snapshot of it. The docstring says a run appending to the thread at the same time is safe, while forking or replaying from a checkpoint being deleted is not. The checkpoint that is kept loses its parent, because the parent is deleted. `prune("monday")` with a bare string raises `TypeError`: pass a list. In 3.2.0, `keep_latest` also refuses threads that use the new beta `DeltaChannel`, because their latest value is rebuilt from older checkpoints. This course doesn't use it.

**One saver object, one query at a time.** The synchronous `PostgresSaver` holds a lock around every database call, with a single connection and with a pool alike. A pool still helps, because it replaces broken connections and one pool can serve both classes, but it does not make one saver object run checkpoint queries in parallel.

**Enabling the extension may need rights.** `setup()` creates the `vector` extension only if it is not enabled yet. On a managed database where your user may not create extensions, an administrator can run `CREATE EXTENSION vector` once, and the migration then finds it and skips the step.

**Search runs an exact scan.** Besides the column, `setup()` builds an HNSW index on the vectors, a structure pgvector uses for fast approximate search. A comment in the 3.2.0 source says the store's search queries do not use such indexes today, because of how they combine the vector order with other conditions, so Postgres compares every vector in the namespace. The results are exact, and the cost grows with the number of items in the searched namespace. For a few memories per user, that does not matter.

**Order of search results without a query.** A search with no `query=` returns items by `updated_at`, newest first. The stores guide says so, and also warns not to rely on any order across store implementations. The lesson sorts the items by key itself before printing them.

**Store values are `jsonb`.** Besides key order, `jsonb` keeps only the last value for a duplicate key. Values go in and out as JSON, so store data a JSON encoder understands: strings, numbers, booleans, lists and dicts. Checkpoints are different: they go through the same serializer as in 5.2, [JsonPlusSerializer](../../../GLOSSARY.md#jsonplusserializer), so messages and dataclasses are fine in state.

**The tests run without Postgres.** `verify` runs the lesson's tests before it starts any service, so they use in-memory stand-ins. They can't check what only a server does: `setup()`, the `vector(6)` column, the `jsonb` key order, `prune`. The live run checks those. One stand-in difference showed up while writing the tests: `InMemoryStore.list_namespaces()` keeps listing a namespace after all its items are deleted, so the tests check `search` results instead.

## Common mistakes

> [!WARNING]
> **Forgetting `setup()` on a new database.** Unlike `SqliteSaver`, the Postgres classes never create their tables on their own. The first query on their tables fails with `psycopg.errors.UndefinedTable: relation "checkpoints" does not exist`, or `relation "store"` on the store side (third experiment). Run `setup()` for both classes in your deploy or at startup.

> [!WARNING]
> **A pool without `autocommit=True`.** `setup()` builds indexes with `CREATE INDEX CONCURRENTLY`, which fails inside a transaction: `ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`. On an already migrated database everything seems to work, so the mistake surfaces only on the next fresh database (fourth experiment). Give the pool `kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}`. The same goes for a connection you open yourself with `psycopg.connect`.

> [!WARNING]
> **A Postgres server without pgvector.** With `index=`, `store.setup()` on the plain `postgres` image fails with `extension "vector" is not available`. Use an image or a managed service that includes pgvector, or create the store without an index if you don't need semantic search.

> [!WARNING]
> **Changing the embedding after `setup()`.** A different vector length makes every indexed `put` fail with `psycopg.errors.DataException: expected 6 dimensions, not 7`, and `setup()` will not fix the column (fifth experiment). A different model with the same length fails silently instead: old and new vectors are not comparable, and the scores become meaningless. Re-embed as a planned migration.

> [!WARNING]
> **A new thread_id per process.** The conversation is still in the database, but nothing points to it any more. Keep the thread_id with the user's session (second experiment).

> [!WARNING]
> **Using the graph after the `with` block.** `from_conn_string` closes its connection when the block ends, exactly like `SqliteSaver.from_conn_string` in 5.2. Open the connection or pool for the lifetime of the application, not for one function call.

> [!WARNING]
> **A connection string in the code.** The URL contains the database password. Read it from the environment or a secret store, as `open_postgres` does, and keep `.env` out of version control.

> [!TIP]
> To see what LangGraph wrote, connect with `psql`: from the course root, `docker compose exec postgres psql -U codelab` and then, for example, `SELECT thread_id, count(*) FROM checkpoints GROUP BY thread_id;`. Read freely, but leave writes to the classes: the table layout is theirs and can change with a migration.

## Experiments

Each experiment starts from the lesson's original code. Run `./run.sh 5.6` from the course root, and guess the result before you open the explanation. For the experiments that run a command by hand, first go to the lesson directory and set the URL from `.env`: `export POSTGRES_URL=postgresql://codelab:codelab@localhost:13682/codelab`.

1. Remove the reset: after a normal run, comment out the `reset_demo(checkpointer, store)` call in `demo`, and run the lesson once more.

   <details><summary>What happens and why</summary>

   The new run continues the previous one. The reset runs at the start of a run, not at the end, so the last run's threads and memories are still in Postgres. Monday's process starts with `thread monday starts with 6 messages` and answers `Noted: sci-fi (already like).` and `Noted: mystery (avoid -> like).`, because Ada's memories from Tuesday are still in the store. Tuesday starts with 8 messages. Bob's first request gets `Try: The Hobbit (fantasy).` instead of "Tell me a genre", because his fantasy memory survived. The counts become `monday=12, tuesday=16, bob-1=12` messages and `monday=10, tuesday=13, bob-1=18` checkpoints (Monday and Tuesday had been pruned to 1, Bob had not). The line "old demo threads and memories removed" still prints, now wrongly. Postgres outlives every process, which is the whole point, and also why a demo has to clean up after itself. Put the call back (uncomment the line), and run once more to get back to the normal output.

   </details>

2. Be another process: after a normal run, run one step by hand from the lesson directory: `uv run --package l5-6-postgres-persistence python -m l5_6_postgres_persistence monday-evening`. Then run it again.

   <details><summary>What happens and why</summary>

   The first time it prints `thread monday starts with 6 messages` and `bot> Try: Dune (sci-fi).`. Only Dune, because Ada asked to skip mystery on Tuesday and the store remembers it, while in the demo this step ran before Tuesday. The second time the count is 8. Your terminal is just one more process with the URL and the thread_id, and that is all it takes to continue the conversation. Lose the thread_id and you lose the conversation, so store it with the user's session. A typo in the step name (`nope`) raises `ValueError: unknown step 'nope'`. No code changed, so there is nothing to undo, but the next `./run.sh 5.6` resets the threads anyway.

   </details>

3. Forget `setup()` on a new database: from the course root, run `docker compose exec postgres createdb -U codelab fresh`. Comment out the two `setup()` calls in `demo`, and run the lesson by hand with `export POSTGRES_URL=postgresql://codelab:codelab@localhost:13682/fresh`.

   <details><summary>What happens and why</summary>

   The `tables:` line is empty, and the run stops in `reset_demo` with `psycopg.errors.UndefinedTable: relation "checkpoints" does not exist`, raised by `delete_thread`'s `DELETE FROM checkpoints`. Unlike `SqliteSaver`, the Postgres classes never create their tables on their own. Put the two calls back and run again on the same database: the eight tables appear and the run completes. Run it once more: `setup()` finds every migration recorded and does nothing, which is why calling it again is harmless. Undo the change and set `POSTGRES_URL` back to the `codelab` database. You can drop the test database with `docker compose exec postgres dropdb -U codelab fresh`.

   </details>

4. Share one pool, and forget autocommit: add `from psycopg_pool import ConnectionPool` to the imports. In `open_postgres`, replace the `with (...)` block after the `url` line with:

   ```python
   with ConnectionPool(url, min_size=1, max_size=4) as pool:
       yield PostgresSaver(pool), PostgresStore(pool, index=MEMORY_INDEX)
   ```

   Also comment out the table listing in `demo`: the `rows = checkpointer.conn.execute(...)` statement and the `print("  tables: ...")` line. Run the lesson on the course database, then on a new one (`createdb -U codelab fresh2` as in the third experiment, with `POSTGRES_URL` pointing to it). Finally add `kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}` to the `ConnectionPool(...)` call (with `from psycopg.rows import dict_row`) and run on `fresh2` again.

   <details><summary>What happens and why</summary>

   The table listing has to go first: `checkpointer.conn` is now the pool, and a pool has no `execute`. Left in, the run stops with `AttributeError: 'ConnectionPool' object has no attribute 'execute'`. With it out, the course database prints the usual output without the `tables:` line. The pool seems fine, because the tables were created long ago. On `fresh2`, `checkpointer.setup()` fails with `psycopg.errors.ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`: without autocommit, every pooled connection runs inside a transaction. The failed setup is rolled back, so after adding the `kwargs` the same new database works, with one pool serving both classes and the same output. That is the setup a web server uses. Undo the changes, set `POSTGRES_URL` back, and drop `fresh2` if you like.

   </details>

5. Change the embedding after setup: in [assistant.py](../src/l5_6_postgres_persistence/assistant.py), add a sixth theme to `THEMES`, for example `"romance": {"love", "romance", "heart"},`. `MEMORY_INDEX["dims"]` is `len(THEMES) + 1`, so it becomes 7. Run the lesson on the course database.

   <details><summary>What happens and why</summary>

   Setup prints the usual eight tables and the reset succeeds, but the `monday` process fails on Ada's first sentence with `psycopg.errors.DataException: expected 6 dimensions, not 7`, and the parent stops with `CalledProcessError`. `store.setup()` did nothing, because the vector migration that created the `vector(6)` column is already recorded. `InMemoryStore` never checked `dims`, but a database column is fixed. Switching embedding models in production means embedding everything again into a new column or table, so plan it as a migration. Undo the change, and the lesson works again. (On a database you can throw away, dropping `store_vectors` and the rows of `vector_migrations` would let `setup()` recreate the column with the new size.)

   </details>

## Summary

- `PostgresSaver` and `PostgresStore`, from `langgraph-checkpoint-postgres`, keep a graph's checkpoints and long-term memories in a Postgres server. They implement the same interfaces as the in-memory classes, so the graph and its nodes don't change, and any process that has the URL and a thread_id can continue a conversation.
- `from_conn_string(url)` is a context manager that opens one connection with `autocommit=True`, `row_factory=dict_row` and `prepare_threshold=0`. A server shares a `ConnectionPool` instead, and the pool needs the same three settings.
- `setup()` is an explicit, repeatable schema migration. It must run before first use, on every new database, and belongs in the deploy, not in each request.
- `PostgresStore(index=...)` keeps embeddings in a pgvector column of length `dims`. The server needs the pgvector extension, and `dims` is fixed once `setup()` has run.
- Checkpoints only grow. Write fewer with `durability="exit"`, or delete old ones with `prune(...)` from a maintenance job. Both give up history.

## Self-check

1. A colleague replaces `SqliteSaver.from_conn_string("chat.db")` with `PostgresSaver.from_conn_string(url)` and changes nothing else. On their laptop's fresh database the first request fails. Why, and what is the fix?

   <details><summary>Answer</summary>

   `SqliteSaver` creates its tables on first use. `PostgresSaver` does not: its tables come from `setup()`, which the user must call the first time. Without it, the first query on their tables fails with `relation "checkpoints" does not exist`. Call `checkpointer.setup()` (and `store.setup()` for a store) once, as part of the deploy or at startup. Calling it again later is harmless.

   </details>

2. Process A ran turn 1 of thread `"chat-7"` and exited. Process B, on another machine, gets turn 2. What does B need to continue the conversation, and what must it not do?

   <details><summary>Answer</summary>

   B needs the database URL and the same thread_id, `"chat-7"`. With those, `PostgresSaver` loads the thread's latest checkpoint and `add_messages` appends turn 2. B must not make up a new thread_id, for example with `uuid4()`: the conversation would start empty, even though turn 1 is still in the database.

   </details>

3. A service runs fine for months with a `ConnectionPool` for both classes. A new staging environment with an empty database fails at startup with `CREATE INDEX CONCURRENTLY cannot run inside a transaction block`. What is wrong, and why didn't it show up before?

   <details><summary>Answer</summary>

   The pool's connections were opened without `autocommit=True`, so each statement runs inside a transaction, and Postgres refuses `CREATE INDEX CONCURRENTLY` there. On the old database every migration had already been applied, so `setup()` had nothing to do and never ran that statement. Pass `kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}` to the pool.

   </details>

4. Why does the parent print `{'note': ..., 'genre': ..., 'stance': ...}` when `remember` wrote the keys in the order genre, stance, note?

   <details><summary>Answer</summary>

   `PostgresStore` keeps values in a `jsonb` column, and `jsonb` does not keep the order of object keys. The dict is equal to what was written; only its printed order differs. Never rely on the key order of a stored dict.

   </details>

5. After `prune(["monday"], strategy="keep_latest")`, thread `monday` has one checkpoint. Did Ada's conversation lose messages? What did it lose?

   <details><summary>Answer</summary>

   No messages were lost: the newest checkpoint holds the whole current state, so `get_state` still shows all 6. What is gone is the history: the earlier checkpoints, which you would need to inspect or go back to earlier steps of the thread.

   </details>

## Further reading

- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence), LangGraph docs: checkpointers versus stores, and troubleshooting notes on in-memory savers and checkpoint growth.
- [Memory](https://docs.langchain.com/oss/python/langgraph/add-memory), LangGraph docs: `PostgresSaver` and `PostgresStore` examples with `from_conn_string` and `setup()`, and the advice to run migrations as a dedicated deployment step.
- [Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers), LangGraph docs: the checkpointer libraries, with Postgres as the production choice.
- [Stores](https://docs.langchain.com/oss/python/langgraph/stores), LangGraph docs: persistent stores for production and the result order of `PostgresStore`.
- [`langgraph-checkpoint-postgres` README](https://github.com/langchain-ai/langgraph/blob/1.2.16/libs/checkpoint-postgres/README.md) at tag 1.2.16: `setup()` on first use, and the `autocommit=True` and `dict_row` settings it asks for on connections you open yourself.
- [`PostgresSaver` source](https://github.com/langchain-ai/langgraph/blob/1.2.16/libs/checkpoint-postgres/langgraph/checkpoint/postgres/__init__.py) and [its migrations](https://github.com/langchain-ai/langgraph/blob/1.2.16/libs/checkpoint-postgres/langgraph/checkpoint/postgres/base.py) at tag 1.2.16 (langgraph-checkpoint-postgres 3.2.0): `from_conn_string`, `setup`, `delete_thread`, `prune` and the table definitions.
- [`PostgresStore` source](https://github.com/langchain-ai/langgraph/blob/1.2.16/libs/checkpoint-postgres/langgraph/store/postgres/base.py) at tag 1.2.16: the store and vector migrations, `pool_config`, the cosine score and the note on ANN indexes.
- [Connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html), psycopg docs: `ConnectionPool`, its `kwargs`, and what happens to broken connections.
- [pgvector](https://github.com/pgvector/pgvector): the `vector` type, the `<=>` cosine distance operator, exact versus approximate search, and the Docker images.
- [JSON Types](https://www.postgresql.org/docs/17/datatype-json.html), PostgreSQL 17 docs: `jsonb` does not keep key order or duplicate keys.
- [agent-service-toolkit, `src/memory/postgres.py`](https://github.com/JoshuaC215/agent-service-toolkit/blob/main/src/memory/postgres.py): a production-style service that opens one async pool per class with `autocommit` and `dict_row` and calls `setup()` at startup.
- [LangGraph Tutorial: Build a ReAct Agent With the v1.0 API](https://agentsindex.ai/blog/langgraph-tutorial), agentsindex.ai: recommends Postgres-backed checkpointing for cloud deployments. It builds its agent with the deprecated `create_react_agent`, so don't copy its agent code.

"""Live run on Postgres: the same assistant, with both memories in a database.

A parent process prepares the tables, four child processes hold the
conversations, and the parent reads everything back. Only the database
connects them: no Python object survives from one process to the next.

Needs POSTGRES_URL and a Postgres server with the pgvector extension
(`docker compose up -d postgres` in the course root).
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.store.postgres import PostgresStore

from l5_6_postgres_persistence.assistant import (
    MEMORY_INDEX,
    UserContext,
    build_graph,
    genres_namespace,
)

# The child processes run this package again: `python -m l5_6_postgres_persistence <step>`.
PACKAGE = "l5_6_postgres_persistence"
# One child process per step, in this order.
STEPS = ["monday", "monday-evening", "tuesday", "bob"]
# The demo's conversations and users (reset_demo removes only these).
THREADS = ["monday", "tuesday", "bob-1"]
USERS = ["ada", "bob"]


# region connect
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


# endregion


# region chat_helper
def chat(graph: CompiledStateGraph, thread_id: str, user_id: str, text: str) -> None:
    """Send one user message on a thread and print the exchange."""
    # thread_id goes in config (which conversation); user_id goes in context
    # (whose memory). They are different keys on purpose.
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(
        {"messages": [HumanMessage(text)]}, config, context=UserContext(user_id=user_id)
    )
    print(f"  {user_id}> {text}")
    print(f"  bot> {result['messages'][-1].content}")


def message_count(graph: CompiledStateGraph, thread_id: str) -> int:
    """Return how many messages the checkpointer holds for a thread."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    return len(graph.get_state(config).values.get("messages", []))


# endregion


# region scenes
def play_scene(step: str, graph: CompiledStateGraph) -> None:
    """Play one step of the story on the given graph.

    The scripts are 5.5's. Only Monday's third message moved into its own
    step, on the same thread. play_scene gets a graph and knows nothing about
    Postgres, so the tests run it on in-memory backends.
    """
    match step:
        case "monday":
            # region monday
            print(f"  thread monday starts with {message_count(graph, 'monday')} messages")
            chat(graph, "monday", "ada", "I love sci-fi: robots and distant planets.")
            chat(graph, "monday", "ada", "I like mystery too, a detective in ancient Rome.")
            # endregion
        case "monday-evening":
            # region monday_evening
            # The same thread_id in a different process. The 4 messages come
            # from Postgres, and add_messages appends the new turn to them.
            print(f"  thread monday starts with {message_count(graph, 'monday')} messages")
            chat(graph, "monday", "ada", "Any book for tonight?")
            # endregion
        case "tuesday":
            # region tuesday
            # A new thread with an empty history, but Monday's memories are in
            # the store. That is the 5.5 behaviour, now across processes.
            print(
                f"  thread tuesday starts with {message_count(graph, 'tuesday')} messages;"
                f" thread monday holds {message_count(graph, 'monday')}"
            )
            chat(graph, "tuesday", "ada", "Something with a spaceship, please.")
            chat(graph, "tuesday", "ada", "I am in the mood for a whodunit.")
            chat(graph, "tuesday", "ada", "Please skip mystery for now.")
            chat(graph, "tuesday", "ada", "I am in the mood for a whodunit.")
            # endregion
        case "bob":
            # region bob
            chat(graph, "bob-1", "bob", "Recommend something.")
            chat(graph, "bob-1", "bob", "I love fantasy: dragons, wizards and an old king.")
            chat(graph, "bob-1", "bob", "Anything with a wizard?")
            # endregion
        case _:
            raise ValueError(f"unknown step {step!r}")


# endregion


# region child_process
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


# endregion


# region reset_demo
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


# endregion


def demo() -> None:
    """Prepare the tables, run every step in its own process, then read it all back."""
    with open_postgres() as (checkpointer, store):
        # region setup_tables
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
        # endregion
    print()

    for step in STEPS:
        run_process(step)
        print()

    with open_postgres() as (checkpointer, store):
        # This process never ran a conversation, yet everything is there.
        graph = build_graph(checkpointer, store)

        # region inspect_store
        print("== back in the parent: what Postgres holds ==")
        # The values come back with their keys in a different order ('note',
        # 'genre', 'stance'): Postgres jsonb stores object keys in its own
        # order (shorter keys first). Never rely on the key order of a stored
        # dict. Timestamps are left out because they change on every run.
        print(f"  namespaces: {store.list_namespaces()}")
        for user_id in USERS:
            items = sorted(store.search(genres_namespace(user_id)), key=lambda i: i.key)
            for item in items:
                print(f"  {item.namespace} {item.key!r}: {item.value}")
        ns = genres_namespace("ada")
        print(f"  get({ns}, 'sci-fi').value = {store.get(ns, 'sci-fi').value}")
        print(f"  get({ns}, 'fantasy') = {store.get(ns, 'fantasy')}")
        counts = ", ".join(f"{thread}={message_count(graph, thread)}" for thread in THREADS)
        print(f"  messages per thread: {counts}")
        # endregion

        print()
        # region keys_vs_meaning
        print("== Keys versus meaning ==")
        # The cosine similarity is now computed inside Postgres by pgvector:
        # score = 1 - (embedding <=> query), where <=> is pgvector's cosine
        # distance. The numbers match InMemoryStore to two decimals. setup()
        # also built an HNSW index on the vectors, but the 3.2.0 source says
        # search does not use ANN indexes today (its query shape forces an
        # exact scan), so the results are exact.
        print(f"  get({ns}, 'space') = {store.get(ns, 'space')}")
        hits = store.search(ns, query="space robots")
        print(
            f"  search({ns}, query='space robots'): "
            + ", ".join(f"{i.key}={i.score:.2f}" for i in hits)
        )
        # endregion

        print()

        # region checkpoint_growth
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
        # endregion


def main() -> None:
    """Run one step when given its name (a child process), else the whole demo."""
    if len(sys.argv) == 2:
        run_step(sys.argv[1])
    else:
        demo()


if __name__ == "__main__":
    main()

"""Live run: the calculator agent with a SQLite checkpointer, across real processes.

The program has two roles, chosen by its command-line arguments:

- ``python -m l5_2_sqlite_checkpointer`` runs the demo (the parent process).
- ``python -m l5_2_sqlite_checkpointer <step> <db_path>`` runs one step as a
  child process, on the SQLite file at ``db_path``.

The parent starts every step as a separate Python process. Nothing is shared
between them except the database file.
"""

import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

# SqliteSaver comes from the langgraph-checkpoint-sqlite package (3.1.2), a
# separate install from langgraph itself.
from langgraph.checkpoint.sqlite import SqliteSaver

# Durability is Literal["sync", "async", "exit"]: when checkpoints are written.
from langgraph.types import Durability

from l5_2_sqlite_checkpointer.chatbot import build_graph, make_model, tool_call

# The package name, used to start this same program as a child process.
PACKAGE = "l5_2_sqlite_checkpointer"


def describe(m: AnyMessage) -> str:
    """Return a one-line description of a message (never its id: ids change per run)."""
    if isinstance(m, AIMessage) and m.tool_calls:
        calls = []
        for tc in m.tool_calls:
            args = ", ".join(f"{k}={v}" for k, v in tc["args"].items())
            calls.append(f"{tc['name']}({args}) [{tc['id']}]")
        return "AIMessage asks for " + ", ".join(calls)
    if isinstance(m, ToolMessage):
        return f"ToolMessage [{m.tool_call_id}] {m.name} = {m.content}"
    return f"{type(m).__name__}: {m.content}"


class CalculatorClient:
    """Stands for a live object, such as an API client or a database connection.

    People are tempted to keep such objects in state. A checkpointer cannot
    save them (see the serialization section of demo()).
    """


# region run_turn
def run_turn(
    db_path: str,
    thread_id: str,
    question: str,
    script: Iterable[AIMessage],
    durability: Durability = "async",
) -> None:
    """Run one turn of a thread against the SQLite file and print what it holds.

    ``durability`` decides when checkpoints reach the file:

    - ``"async"`` (the default) writes each checkpoint in the background while
      the next step already runs.
    - ``"sync"`` waits until the checkpoint is written before the next step
      starts: the safest mode, but every step pays for a write.
    - ``"exit"`` writes only once, when the run ends: the cheapest mode, but a
      process that dies mid-run leaves nothing of that run.
    """
    # The thread_id is the only key to the saved conversation. A new process
    # can resume only if it knows the same thread_id, so a real app stores it
    # with the user or session (never a fresh uuid4 per process). SqliteSaver
    # stores it as TEXT (str(thread_id)), so 1 and "1" are the same thread.
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    # This `with` line is the one change from 5.1, where __main__ did
    # `checkpointer = InMemorySaver()`: build_graph takes any
    # BaseCheckpointSaver. from_conn_string is a @contextmanager. It opens
    # sqlite3.connect(db_path, check_same_thread=False) (langgraph writes
    # checkpoints from worker threads; SqliteSaver guards the connection with
    # a lock), yields a saver, and closes the connection when the block ends.
    # So the graph must be used inside the block.
    # The tables (checkpoints, writes) are created on first use: SQLite needs
    # no setup() call (its docstring says it is called automatically).
    # ":memory:" instead of a path gives a database that dies with the connection.
    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        graph = build_graph(make_model(script), checkpointer)

        # What did this process find in the file before doing anything?
        saved = graph.get_state(config).values.get("messages", [])
        print(f"  loaded from the file: {len(saved)} messages", flush=True)

        # The input holds only the new question; add_messages appends it to
        # the messages loaded from the file.
        result = graph.invoke({"messages": [HumanMessage(question)]}, config, durability=durability)

        # Print only this turn's messages: the earlier ones are in the file.
        for m in result["messages"][len(saved) :]:
            print(f"  {describe(m)}")

        # checkpointer.list reads the saved checkpoints of the thread, newest first.
        n = len(list(checkpointer.list(config)))
        print(f"  the thread now holds {len(result['messages'])} messages in {n} checkpoints")


# endregion


# region crash_script
def crash_script() -> Iterator[AIMessage]:
    """Yield one tool call, then kill the process on the second model call.

    This simulates pulling the plug: the process dies at once, with no
    exception, no ``finally`` blocks and no clean exit, like ``kill -9`` or a
    power cut. make_model accepts any iterable, including a generator, so the
    second model call runs the code after the ``yield``.
    """
    yield tool_call("add", "call_1", a=3, b=4)
    # os._exit drops buffered output, so flush what was printed so far.
    sys.stdout.flush()
    os._exit(1)


# endregion


# region run_step
def run_step(step: str, db_path: str) -> None:
    """Run one step of the demo in this (child) process.

    Each process builds its own model with only the replies of its own turn.
    In 5.1 one model and one script served both turns; here turn 2 runs in a
    process that never saw turn 1's script. The scripts are built inside this
    function because the fake model mutates the scripted messages.
    """
    match step:
        case "turn1":
            run_turn(
                db_path,
                "chat-1",
                "What is 3 + 4?",
                [tool_call("add", "call_1", a=3, b=4), AIMessage("3 + 4 is 7.")],
            )
        case "turn2":
            run_turn(
                db_path,
                "chat-1",
                "Now multiply that by 2.",
                [tool_call("multiply", "call_2", a=7, b=2), AIMessage("7 * 2 is 14.")],
            )
        case "crash-sync":
            run_turn(db_path, "crash-sync", "What is 3 + 4?", crash_script(), durability="sync")
        case "crash-exit":
            run_turn(db_path, "crash-exit", "What is 3 + 4?", crash_script(), durability="exit")
        case _:
            raise ValueError(f"unknown step {step!r}")


def run_process(step: str, db_path: str) -> int:
    """Run one step in a new Python process and return its exit code.

    This is a real new Python process, with no memory shared with the parent:
    only the SQLite file connects them. No check=True, because the crash steps
    exit with code 1. The child inherits stdout, so the header is flushed first
    to keep the output in order.
    """
    print(f"== process: {step} ==", flush=True)
    return subprocess.run([sys.executable, "-m", PACKAGE, step, db_path]).returncode


# endregion


def demo() -> None:
    """Run the parent process: start the steps as child processes and inspect the file."""
    # A fresh file per run, so the output is reproducible and nothing is left
    # in the lesson directory. Never print the path: it changes per run.
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "checkpoints.sqlite")

        # region two_processes
        # Process 1 runs turn 1 and exits. Process 2 starts with the 4 messages
        # process 1 saved, add_messages appends the new question, and the step
        # counter and checkpoint list continue (10 checkpoints in the end).
        run_process("turn1", db_path)
        print()
        run_process("turn2", db_path)
        print()
        # endregion

        # region crash_demo
        # Two processes die halfway through a turn, one per durability mode.
        for step in ("crash-sync", "crash-exit"):
            code = run_process(step, db_path)
            print(f"  the process died, exit code {code}")
            print()

        # Now the parent opens the file and looks at what each crash left.
        with SqliteSaver.from_conn_string(db_path) as checkpointer:
            # Only for get_state: the model is never called.
            graph = build_graph(make_model([]), checkpointer)
            print("== after the crashes ==")
            # With "sync", every checkpoint up to the last finished step was on
            # disk before the next step started: the thread holds the question,
            # the tool call and the tool result, and next=('call_model',) says
            # where to continue. With "exit", the process died before the run's
            # only write, so the thread does not exist.
            # "async" (not shown: its result varies from run to run) can lose
            # the newest checkpoints in a hard crash. An ordinary exception is
            # different: the run still exits through langgraph, and even "exit"
            # saves the final checkpoint then.
            for thread_id in ("crash-sync", "crash-exit"):
                snap = graph.get_state({"configurable": {"thread_id": thread_id}})
                n = len(snap.values.get("messages", []))
                step = snap.metadata["step"] if snap.metadata else None
                print(f"  {thread_id}: {n} messages  next={snap.next}  step={step}")
            # endregion
            print()

            # region saved_threads
            print("== threads in the file ==")
            # list(None) lists the checkpoints of every thread in the database.
            # crash-exit is absent because nothing of it was saved.
            counts = Counter(c.config["configurable"]["thread_id"] for c in checkpointer.list(None))
            for thread_id, n in sorted(counts.items()):
                print(f"  {thread_id}: {n} checkpoints")
            # endregion
            print()

            # region serialization
            print("== what a checkpoint can hold ==")
            # checkpointer.serde is the serializer that writes every checkpoint
            # (JsonPlusSerializer, msgpack-based). It knows messages,
            # primitives, dicts/lists, datetime, UUID, Enum, sets, dataclasses
            # and pydantic models. Anything else fails with TypeError when the
            # checkpoint is written, so state must hold data, not live objects.
            # InMemorySaver serializes the same way.
            # Custom classes (dataclasses, pydantic) are restored by import path
            # in the process that loads them, so they must be importable there.
            # langgraph-checkpoint 4.3.0 logs "Deserializing unregistered type
            # ..." for them and blocks them under LANGGRAPH_STRICT_MSGPACK=true.
            values = (
                HumanMessage("What is 3 + 4?"),
                datetime(2026, 1, 1, tzinfo=UTC),
                CalculatorClient(),
            )
            for value in values:
                try:
                    kind, _ = checkpointer.serde.dumps_typed(value)
                    print(f"  {type(value).__name__}: saved as {kind}")
                except TypeError as e:
                    print(f"  {type(value).__name__}: TypeError: {e}")
            # endregion


def main() -> None:
    """Run the demo, or one step when called as ``<step> <db_path>``."""
    if len(sys.argv) == 3:
        run_step(sys.argv[1], sys.argv[2])
    else:
        demo()


if __name__ == "__main__":
    main()

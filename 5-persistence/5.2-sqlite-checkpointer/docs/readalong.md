# 5.2 Durable Checkpoints with SQLite — code walkthrough

The program runs the calculator agent from 5.1 with a `SqliteSaver`, so each conversation is saved in a SQLite file. The parent process starts real child processes on one file. Turn 1 runs in one process and turn 2 in a second one, which loads turn 1 from the file. Then two processes die halfway through a turn, one with `durability="sync"` and one with `durability="exit"`, and the parent shows what each one left on disk. Run it with `./run.sh 5.2` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 5.1

- [tools.py](../src/l5_2_sqlite_checkpointer/tools.py) and [chatbot.py](../src/l5_2_sqlite_checkpointer/chatbot.py) are copied from 5.1. The only change is the package name in the import on [line 27 of chatbot.py](../src/l5_2_sqlite_checkpointer/chatbot.py#L27). They are explained in the [5.1 read-along](../../5.1-checkpointers-and-threads/docs/readalong.md).
- In 5.1, `__main__` created one `InMemorySaver()` for the whole process. Here the saver is opened in [`run_turn`](../src/l5_2_sqlite_checkpointer/__main__.py#L94) with `SqliteSaver.from_conn_string(db_path)`. `build_graph` already took any saver, so nothing else had to change.
- The program now has two roles: parent ([`demo`](../src/l5_2_sqlite_checkpointer/__main__.py#L182-L261)) and child ([`run_step`](../src/l5_2_sqlite_checkpointer/__main__.py#L136-L164)). [`main`](../src/l5_2_sqlite_checkpointer/__main__.py#L264-L269) picks the role.
- Each child builds its own model with only its own turn's replies ([lines 145-158](../src/l5_2_sqlite_checkpointer/__main__.py#L145-L158)). In 5.1, one script served every turn in one process.
- [`crash_script`](../src/l5_2_sqlite_checkpointer/__main__.py#L118-L129) is new. It kills the process halfway through a turn.
- [pyproject.toml](../pyproject.toml#L9) adds `langgraph-checkpoint-sqlite==3.1.2`. This is a separate package: `langgraph` does not install it.
- [test_sqlite_checkpointer.py](../tests/test_sqlite_checkpointer.py) is new. 5.1's tests are not copied.

## [\_\_main\_\_.py](../src/l5_2_sqlite_checkpointer/__main__.py)

The whole lesson is in this file. Read it in this order: the helpers at the top, then the child side (`run_turn`, `crash_script`, `run_step`), then the parent side (`run_process`, `demo`).

### Imports and helpers

- [Line 27](../src/l5_2_sqlite_checkpointer/__main__.py#L27) imports `SqliteSaver` from `langgraph.checkpoint.sqlite`. Python finds this module in the extra package. `SqliteSaver` is a `BaseCheckpointSaver`, just like `InMemorySaver`. It has the same `get_tuple`, `list`, `put` and `put_writes` methods, but it keeps the checkpoints in two tables, `checkpoints` and `writes`.
- [Line 30](../src/l5_2_sqlite_checkpointer/__main__.py#L30) imports `Durability` only for the type hint of `run_turn`.
- [`PACKAGE`](../src/l5_2_sqlite_checkpointer/__main__.py#L35) is the module name that the parent passes to `python -m` to start this same program again as a child.
- [`describe`](../src/l5_2_sqlite_checkpointer/__main__.py#L38-L48) is the same helper as in 5.1.
- [`CalculatorClient`](../src/l5_2_sqlite_checkpointer/__main__.py#L51-L56) is an empty class. It stands for a live object, and the serialization section uses it to show what a checkpoint cannot hold. It is defined at module level so that the test can import it.

### [`run_turn`](../src/l5_2_sqlite_checkpointer/__main__.py#L60-L111)

`run_turn` runs one turn of one thread against the file. Every child calls it.

- [Line 82](../src/l5_2_sqlite_checkpointer/__main__.py#L82): the config holds only the `thread_id`. It is the only link between the two processes and the saved conversation. A process that uses a different id would start from an empty thread, even though the old one is still in the file. `SqliteSaver.put` stores `str(thread_id)`, so the int `1` and the string `"1"` address the same row (a test checks this).
- [Line 94](../src/l5_2_sqlite_checkpointer/__main__.py#L94) is the new line. `from_conn_string` is a context manager. On entry it calls `sqlite3.connect(db_path, check_same_thread=False)` and wraps the connection in a saver. On exit it closes the connection. `check_same_thread=False` is needed because langgraph writes checkpoints from worker threads, not only from the thread that opened the connection. The saver puts a lock around the connection so that only one thread uses it at a time. If you call `sqlite3.connect(path)` yourself with the default setting, the first write fails with `sqlite3.ProgrammingError`.
- The graph is used only inside the `with` block ([lines 95-111](../src/l5_2_sqlite_checkpointer/__main__.py#L95-L111)). After the block, the connection is closed, and any further `invoke` or `get_state` on this graph would fail.
- No `setup()` call is needed. The first database access calls it: it switches the file to WAL journal mode and runs `CREATE TABLE IF NOT EXISTS` for both tables. So a missing file simply becomes a new, empty database.
- [Line 98](../src/l5_2_sqlite_checkpointer/__main__.py#L98) reads the thread before the run. This shows what the process found in the file: 0 messages in turn 1 and 4 in turn 2. `flush=True` on [line 99](../src/l5_2_sqlite_checkpointer/__main__.py#L99) matters for the crash steps. When stdout is a pipe, Python buffers it, and `os._exit` would throw the buffer away.
- [Line 103](../src/l5_2_sqlite_checkpointer/__main__.py#L103): `durability` is an argument of `invoke`, not of `compile`. So the same compiled graph can run one call with `"sync"` and the next with `"exit"`. It controls only when checkpoints reach the saver. The final state is the same in all three modes (see `test_durability_modes`).
- [Line 106](../src/l5_2_sqlite_checkpointer/__main__.py#L106) prints from `len(saved)` on. `invoke` returns the whole thread, and the earlier messages are already in the file.
- [Line 110](../src/l5_2_sqlite_checkpointer/__main__.py#L110) counts this thread's checkpoints in the file: 5 after turn 1 and 10 after turn 2. The step numbers continue across processes, because the new process starts from the last saved checkpoint.

### [`crash_script`](../src/l5_2_sqlite_checkpointer/__main__.py#L118-L129)

`crash_script` is a generator used as the model's script. The fake model calls `next()` on it once per model call. The first call gets the tool call on [line 126](../src/l5_2_sqlite_checkpointer/__main__.py#L126). The second call resumes the generator after the `yield` and reaches `os._exit(1)` on [line 129](../src/l5_2_sqlite_checkpointer/__main__.py#L129).

`os._exit` ends the process at once, unlike `sys.exit` or an exception. langgraph gets no chance to react: no `finally` blocks run, and nothing that is queued gets written. So the file shows only what was on disk at that moment. By then, two steps have finished: `call_model` (step 1) and `tools` (step 2). The process dies inside the second `call_model`.

### [`run_step`](../src/l5_2_sqlite_checkpointer/__main__.py#L136-L164) and [`run_process`](../src/l5_2_sqlite_checkpointer/__main__.py#L167-L176)

- `run_step` is the child side. Each `case` is one process's work. `turn1` and `turn2` use the same thread `chat-1`, so turn 2 continues turn 1. The two crash steps each get their own thread ([lines 160](../src/l5_2_sqlite_checkpointer/__main__.py#L160) and [162](../src/l5_2_sqlite_checkpointer/__main__.py#L162)), so the parent can look at them one by one. They differ only in `durability`.
- The scripts are lists built inside each `case`. The turn 2 process never sees turn 1's script. It only needs the replies for its own two model calls, because the history comes from the file.
- `run_process` is the parent side. [Line 176](../src/l5_2_sqlite_checkpointer/__main__.py#L176) starts `sys.executable -m l5_2_sqlite_checkpointer <step> <db_path>`. Under `uv run`, this is the module's virtual environment, with the lesson installed. The child is a new interpreter, so it imports everything again and shares no objects with the parent. It writes straight to the parent's stdout. That is why [line 175](../src/l5_2_sqlite_checkpointer/__main__.py#L175) flushes the header first. The return code is returned, not checked, because the crash steps exit with 1 on purpose.

### [`demo`](../src/l5_2_sqlite_checkpointer/__main__.py#L182-L261)

`demo` is the parent. [Lines 186-187](../src/l5_2_sqlite_checkpointer/__main__.py#L186-L187) put the database in a temporary directory. Each run starts from an empty file, and the directory is deleted at the end, together with any `-wal`/`-shm` files that a crashed child left next to the database.

**Section `two_processes`, [lines 189-197](../src/l5_2_sqlite_checkpointer/__main__.py#L189-L197).** Two child processes run one after another on the same path. In the output, process 2 prints `loaded from the file: 4 messages`. This is the whole point of the lesson: with 5.1's `InMemorySaver`, it would print 0.

**Section `crash_demo`, [lines 199-225](../src/l5_2_sqlite_checkpointer/__main__.py#L199-L225).**

- [Lines 201-204](../src/l5_2_sqlite_checkpointer/__main__.py#L201-L204) run the two crash steps. Each child prints `loaded from the file: 0 messages` and then dies, so the parent prints exit code 1.
- [Line 207](../src/l5_2_sqlite_checkpointer/__main__.py#L207) opens the same file in the parent with a fresh saver. The rest of `demo` runs inside this block.
- [Line 209](../src/l5_2_sqlite_checkpointer/__main__.py#L209) builds a graph with an empty script. `get_state` needs a compiled graph with a checkpointer, but it never calls the model.
- [Line 221](../src/l5_2_sqlite_checkpointer/__main__.py#L221) reads each crashed thread:
  - `crash-sync` has 3 messages (question, tool call, tool result) and `step=2`, with `next=('call_model',)`. With `"sync"`, each checkpoint is written before the next step starts. So the checkpoint after `tools` was safe before the deadly `call_model` began. The thread could be finished later by invoking with `None` on the same thread_id.
  - `crash-exit` has nothing. With `"exit"`, the only write happens when the run ends, and this run never ended. `get_state` of an unknown thread is not an error: it returns empty `values`, `next=()` and `metadata=None`. That is why [line 223](../src/l5_2_sqlite_checkpointer/__main__.py#L223) checks `snap.metadata` before reading `step`.
  - `"async"` is not shown. It writes in the background, so after a hard kill the number of saved checkpoints varies from run to run (1 to 4 of the 4 when the lesson was designed; most often 1 or 2 in later re-runs), so up to 3 of the newest can be lost. An ordinary exception is a different case: langgraph still ends the run itself and saves the last checkpoint, even with `"exit"`.

**Section `saved_threads`, [lines 228-235](../src/l5_2_sqlite_checkpointer/__main__.py#L228-L235).** On [line 232](../src/l5_2_sqlite_checkpointer/__main__.py#L232), `checkpointer.list(None)` reads the checkpoints of every thread in the file instead of one thread. Each item is a `CheckpointTuple`, and its `config` names its thread, so the `Counter` counts checkpoints per thread. `chat-1` has 10. `crash-sync` has 4: the input checkpoint (step -1) and steps 0, 1 and 2. `crash-exit` does not appear at all.

**Section `serialization`, [lines 238-261](../src/l5_2_sqlite_checkpointer/__main__.py#L238-L261).**

- `checkpointer.serde` on [line 257](../src/l5_2_sqlite_checkpointer/__main__.py#L257) is the serializer that the saver uses for every checkpoint. `dumps_typed` returns a pair: a format tag and the bytes. The demo prints only the tag, `msgpack`.
- The message and the `datetime` ([lines 251-252](../src/l5_2_sqlite_checkpointer/__main__.py#L251-L252)) are types the serializer knows. `CalculatorClient()` is not, so `dumps_typed` raises `TypeError: Type is not msgpack serializable`. In a real graph, the same error happens when a node puts such an object into state and the checkpoint is written. The rule is to keep data in state, and to create clients and connections inside the node or pass them in from outside.
- This is not specific to SQLite: `InMemorySaver` uses the same serializer. You notice it more with a file, because a checkpoint is also read back in another process. That process must be able to import any custom class that the checkpoint names.

### [`main`](../src/l5_2_sqlite_checkpointer/__main__.py#L264-L269)

[Line 266](../src/l5_2_sqlite_checkpointer/__main__.py#L266) picks the role by the number of arguments. Two arguments (`<step> <db_path>`) make a child. Anything else runs the demo. An unknown step reaches the `case _` on [line 164](../src/l5_2_sqlite_checkpointer/__main__.py#L164) and raises.

## [test_sqlite_checkpointer.py](../tests/test_sqlite_checkpointer.py)

The tests check the same facts without printing, plus a few that the demo doesn't show.

- [`turn1_script`](../tests/test_sqlite_checkpointer.py#L17-L19) returns new messages on each call, because the fake model changes the ones it returns. [`run_child`](../tests/test_sqlite_checkpointer.py#L22-L26) starts a child step like `run_process` does, but it captures the output.
- [`test_resume_from_file_with_new_saver`](../tests/test_sqlite_checkpointer.py#L29-L46): two separate `with` blocks on one file, in one process. The first saver's connection is closed before the second one opens. [Line 41](../tests/test_sqlite_checkpointer.py#L41) shows that the new saver sees turn 1 before anything runs.
- [`test_two_real_processes`](../tests/test_sqlite_checkpointer.py#L49-L62) runs the `turn1` and `turn2` steps as real processes and then reads the file from the test: 8 messages, `next == ()`.
- [`test_durability_modes`](../tests/test_sqlite_checkpointer.py#L65-L83) uses `":memory:"` ([line 67](../tests/test_sqlite_checkpointer.py#L67)), a SQLite database that exists only while its connection is open. That is enough here, because everything happens inside one block. All three modes give 4 messages. `"sync"` and `"async"` save steps 3 down to -1 (`list` returns newest first). `"exit"` saves only the final checkpoint, step 3 with source `loop` ([lines 78-81](../tests/test_sqlite_checkpointer.py#L78-L81)).
- [`test_hard_crash_per_mode`](../tests/test_sqlite_checkpointer.py#L86-L107) pins the crash results from the demo: 4 checkpoints and `next == ("call_model",)` for `crash-sync`, no checkpoints at all for `crash-exit`. There is no test for `"async"` crashes, because their result changes between runs.
- [`test_thread_rules`](../tests/test_sqlite_checkpointer.py#L110-L123): [line 116](../tests/test_sqlite_checkpointer.py#L116) invokes without a config and gets a `ValueError` that names `thread_id`. [Lines 119-122](../tests/test_sqlite_checkpointer.py#L119-L122) write with `thread_id=1` and read back with `"1"`.
- [`test_serialization`](../tests/test_sqlite_checkpointer.py#L126-L137): a message goes through `dumps_typed` and back through `loads_typed` unchanged, and `CalculatorClient` is rejected with `TypeError`.

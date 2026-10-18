# 10.6 Application Structure and the Local Server — code walkthrough

The program takes the support desk from lesson 8.1 and turns it into a LangGraph application. It starts `langgraph dev` as a child process and talks to it only over HTTP through `langgraph_sdk`: it lists the assistant, runs two tickets on one thread, starts a second thread, then restarts the server and reads the first thread back. Run it with `./run.sh 10.6` from the course root.
The concept itself is explained in the [notes](notes.md).

## Where the code comes from

The example ("support-desk-app") is new, and no later lesson extends it. Its graph is not new: [billing.py](../src/l10_6_local_server/billing.py) is a verbatim copy of 8.1's file, and [desk.py](../src/l10_6_local_server/desk.py) differs only in the import on [line 11](../src/l10_6_local_server/desk.py#L11), which now names this lesson's package. Both are explained in [8.1's read-along](../../../8-multi-agent/8.1-subgraphs-shared-state/docs/readalong.md). Their comments still speak of "section 1 of the run", "experiment 2" and so on; those are 8.1's sections and experiments, not this lesson's.

One thing in `desk.py` matters here: [`build_desk`](../src/l10_6_local_server/desk.py#L57-L86) takes the checkpointer as its only parameter. This lesson relies on that parameter twice, in `graph.py` and in experiment 2.

Nothing in the lesson calls a model or an outside service. The server listens on 127.0.0.1 only, and the switches in `server.py` turn off the few requests the CLI and the server would otherwise send, so the run is fully offline and prints the same lines every time.

## [pyproject.toml](../pyproject.toml)

[Lines 7-13](../pyproject.toml#L7-L13) pin every package exactly. `langgraph-cli[inmem]` on [line 10](../pyproject.toml#L10) provides the `langgraph` command; the `inmem` extra brings the server itself (`langgraph-api`) and its in-memory runtime (`langgraph-runtime-inmem`). Those two are pinned on lines 11-12 as well, because the server behaviour this lesson depends on (the checkpointer check, the port fallback, the saved `.langgraph_api/` folder) lives in them, not in the CLI. `langgraph-sdk` on line 13 is the client; `langgraph` already requires it (`>=0.4.6,<0.5`), and the pin fixes the version the resolver picked.

When uv installs the CLI, it puts a `langgraph` script next to the venv's `python`; `server.py` relies on that.

## [langgraph.json](../langgraph.json)

The application's manifest. `langgraph dev` reads it from the directory it is started in.

- `"dependencies"` on [line 2](../langgraph.json#L2): `"."` means "this directory". For a local path the server puts it on `sys.path` before it loads the graphs. In this workspace the package is already installed in the venv, so the entry matters mainly for `langgraph build`, which installs the dependencies into an image.
- `"graphs"` on [lines 3-5](../langgraph.json#L3-L5) maps a graph id to a `path/to/file.py:name` spec. The id `support_desk` is the name clients use; the part after `:` is the object the server imports from that file, here the factory `make_graph`. For every entry the server creates one assistant named after the id, which section 1 of the run prints.
- `"python_version"` on [line 6](../langgraph.json#L6) does nothing for `langgraph dev`, which runs in the current Python. It chooses the base image for `langgraph build`; it is set to 3.12 to match `requires-python`.

There is no `"env"` key: the server needs no variables from a `.env` file in this lesson.

## [.gitignore](../.gitignore)

Two files the run creates in the lesson directory. `.langgraph_api/` on [line 1](../.gitignore#L1) is where the dev runtime pickles its threads, runs and checkpoints when it shuts down, and loads them back on start; section 4 of the run depends on it. Delete the folder and the server starts empty. `server.log` on [line 2](../.gitignore#L2) is the server's output, written by `running_server`.

## [graph.py](../src/l10_6_local_server/graph.py)

The module `langgraph.json` points at. The server imports this file, not the package's `__main__`.

- [`make_graph`](../src/l10_6_local_server/graph.py#L9-L23) is the entry point. Its comments list the three rules; here is what they mean when the code runs.
- The `checkpointer=None` on [line 23](../src/l10_6_local_server/graph.py#L23) is the important value. On every run the server supplies the run's checkpointer and store itself, keyed by the thread. If the module exported a compiled graph that already had an `InMemorySaver`, `langgraph dev` would refuse to start with a "Heads up!" `ValueError` (experiment 1), because that saver would be ignored once deployed anyway.
- `make_graph` takes no parameters, and that matters too. The server inspects the factory's signature: with one parameter it passes the run's config there. `build_desk` has exactly one parameter, `checkpointer`, so pointing `langgraph.json` at it directly would put the config dict into `compile(checkpointer=...)`, and every run would fail with "Invalid checkpointer provided" (experiment 2). The zero-argument wrapper is the simplest factory that works.
- Because it is a factory, the server builds a fresh graph each time it needs one (each run, each state read). Building the desk is cheap here; work that is expensive should not be done at import time and repeated by the factory.

## [server.py](../src/l10_6_local_server/server.py)

The live run's stand-in for a terminal where you would type `langgraph dev`. It starts the server, waits until it answers and stops it again.

- [`APP_DIR`](../src/l10_6_local_server/server.py#L22) walks up from `server.py` (`src/l10_6_local_server/` → `src/` → the lesson directory). The server is started with this directory as `cwd`, which is how it finds `langgraph.json` and where it writes `.langgraph_api/`. [`LOG_FILE`](../src/l10_6_local_server/server.py#L23) sits next to it.
- [`OFFLINE_ENV`](../src/l10_6_local_server/server.py#L25-L33) holds three switches that are merged into the child's environment. Each one stops a request the CLI or the server would make by itself: a usage event, a version lookup on pypi.org, a trace upload to LangSmith. Without them the run still works on a machine with internet, but it would not be offline.
- [`dev_command`](../src/l10_6_local_server/server.py#L36-L49) builds the command line. [Line 40](../src/l10_6_local_server/server.py#L40) takes the `langgraph` script from the same `bin/` folder as the running `sys.executable`, so the server runs with the same packages and the same version of the lesson code, whatever is on `PATH`. `--no-browser` and `--no-reload` turn off the two things `dev` does for a person at a keyboard: opening Studio, and restarting when a file changes (experiment 5 shows the reload).
- [`port_in_use`](../src/l10_6_local_server/server.py#L56-L63) tries to connect to the port: `connect_ex` returns 0 when something accepts the connection. The check exists because `langgraph dev` does not fail on a busy port; it silently picks another one, and the client, still using the old URL, would reach whatever else is listening there (experiment 3).
- [`running_server`](../src/l10_6_local_server/server.py#L70-L115) is a context manager: the code before `yield` starts the server, the `finally` block stops it, so the server is stopped also when the `with` body raises.
  - [Line 74](../src/l10_6_local_server/server.py#L74) checks the port before the log file is opened or a process exists. The test `test_running_server_refuses_busy_port` checks exactly that order.
  - [Lines 80-86](../src/l10_6_local_server/server.py#L80-L86) start the process. `env={**os.environ, **OFFLINE_ENV}` keeps the rest of the environment (`PATH`, `HOME`, the venv) and overrides only the three switches. `stderr=subprocess.STDOUT` sends both streams to `server.log`, so the run's own output holds only the lesson's lines.
  - The readiness loop on [lines 90-105](../src/l10_6_local_server/server.py#L90-L105) does two things on each pass. `proc.poll()` on line 92 notices a server that has already exited, for example after the checkpointer refusal in experiment 1, and reports its exit code instead of waiting 60 seconds. Then it requests `GET /ok`; while the server is still starting, the connection is refused and the `except` on line 101 just tries again 0.2 s later. A 200 means the graphs are loaded and the API is up.
  - [Line 106](../src/l10_6_local_server/server.py#L106) hands the URL to the `with` body. It is inside the `try`, like the readiness loop, so the `finally` runs whether the server failed to start or the body is done.
  - [Line 110](../src/l10_6_local_server/server.py#L110) sends `SIGINT`, the same signal Ctrl+C sends. The server then shuts down cleanly, and that clean shutdown is when the dev runtime writes `.langgraph_api/`. `proc.kill()` on line 114 is only a fallback for a server that hangs; a killed server gets no chance to shut down cleanly, so the restart in section 4 could not count on finding the thread.

## [client.py](../src/l10_6_local_server/client.py)

The caller's side. It imports only `langgraph_sdk`, so it could run on another machine or in a project that does not have `langgraph` installed. `SyncLangGraphClient` on [line 8](../src/l10_6_local_server/client.py#L8) is used only for type hints; the client object itself comes from `get_sync_client` in `__main__.py`.

- [`ASSISTANT`](../src/l10_6_local_server/client.py#L13) is the graph id from `langgraph.json`. The server accepts a graph id wherever an `assistant_id` is expected and uses the assistant it made for that graph. `test_langgraph_json_is_valid` reads the config with this constant, so the client and the config cannot drift apart unnoticed.
- [`ticket`](../src/l10_6_local_server/client.py#L18-L23) builds the input as plain data. Over HTTP the input is JSON, so a `HumanMessage` object cannot be sent. On the server, the `add_messages` reducer of `DeskState.messages` turns `{"role": "user", "content": ...}` into a `HumanMessage` before `classify` reads `.content`. The same reducer does this in-process too, which `test_json_ticket_runs_in_process` checks.
- [`ask`](../src/l10_6_local_server/client.py#L30-L37) is one call, `client.runs.wait(...)` on [line 37](../src/l10_6_local_server/client.py#L37). It sends `POST /threads/{thread_id}/runs/wait`: the server creates a run on that thread, queues it, runs the graph with the thread's checkpointer and answers when the run is finished, with the thread's final state values. The result is JSON, so the messages come back as dicts (`"type"`, `"name"`, `"content"`), not as message objects. That is why `reply_line` uses `last['name']` rather than `last.name`.
- About errors, the comment on lines 34-36 describes what the run observed in experiment 2: when the graph raised, `ask` returned a dict with an `"__error__"` key and did not raise. In the installed `langgraph-sdk` 0.4.8 the sync `runs.wait` does not inspect the answer itself. It only sends its `raise_error` option (default `True`) to the server and returns whatever the server sends back. (The async client is different: it checks for `"__error__"` and raises.) So with this client, a failed run shows up later, typically as a `KeyError` on `state['category']`, as in experiment 2.
- [`reply_line`](../src/l10_6_local_server/client.py#L43-L46) formats the last message of a state dict. It works on both the `runs.wait` result and a `get_state` snapshot's `values`, which section 4 uses.

## [\_\_main\_\_.py](../src/l10_6_local_server/__main__.py)

The live run. Each section prints a header and the lines that show its point. The port comes from `LANGGRAPH_DEV_PORT` on [line 17](../src/l10_6_local_server/__main__.py#L17) (2024 by default, set in `.env`).

[Lines 19-20](../src/l10_6_local_server/__main__.py#L19-L20) nest two context managers: `running_server` starts and stops the process, `get_sync_client` opens an HTTP client for the URL and closes it again. The client must be closed before the server stops, which the nesting order gives for free.

### Section 1: the assistant ([lines 22-30](../src/l10_6_local_server/__main__.py#L22-L30))

`client.assistants.search(graph_id=ASSISTANT)` on [line 26](../src/l10_6_local_server/__main__.py#L26) lists the assistants of the graph. The program never created one: the server registered `support_desk` at startup from `langgraph.json`, with `metadata.created_by` set to `"system"`.

### Section 2: one thread, two runs ([lines 34-56](../src/l10_6_local_server/__main__.py#L34-L56))

- `client.threads.create()` on [line 40](../src/l10_6_local_server/__main__.py#L40) creates the thread on the server and returns it as a dict; the server generates its `thread_id`. Status `idle` means no run is active on it. Compare with module 5, where a thread was only a `thread_id` string in the config and the saver lived in our process.
- The loop on [lines 43-47](../src/l10_6_local_server/__main__.py#L43-L47) runs both tickets on the same thread. The second run starts from the checkpoint the first one left, so `add_messages` adds two messages to the two already there: the count goes from 2 to 4. The run never passes a checkpointer or `configurable.thread_id`; the server fills both in for every run on the thread.
- `get_state` on [line 48](../src/l10_6_local_server/__main__.py#L48) is the HTTP version of `graph.get_state(config)`: the latest checkpoint's `values` and `next`. The empty `next` means the graph finished. To answer it, the server calls `make_graph` again, which is the "each state read" in `graph.py`'s comment.
- `get_history` on [line 53](../src/l10_6_local_server/__main__.py#L53) returns the thread's checkpoints, newest first. Each run of this graph writes four (the input, the start, `classify`, then `billing` or `general`), so two runs make 8. `limit=100` is there because the SDK's default is 10, which would cut a longer history short. The run prints the count instead of asserting it.
- `client.runs.list` on [line 55](../src/l10_6_local_server/__main__.py#L55) shows that the server keeps runs as objects of their own, each with a status. Both are `success`.

### Section 3: a second thread ([lines 60-65](../src/l10_6_local_server/__main__.py#L60-L65))

A new thread from [line 62](../src/l10_6_local_server/__main__.py#L62) and one ticket on it. The result holds 2 messages, not 6: the state belongs to the thread, and this thread has no checkpoints yet. The ticket has no billing words, so it goes to `general`.

At [line 66](../src/l10_6_local_server/__main__.py#L66) both `with` blocks end: the client is closed, then the server gets `SIGINT` and saves its data.

### Section 4: restart ([lines 69-79](../src/l10_6_local_server/__main__.py#L69-L79))

[Line 74](../src/l10_6_local_server/__main__.py#L74) starts a brand-new `langgraph dev` process on the same port. The port check passes because `proc.wait()` in the previous `running_server` returned only after the old process had exited. `get_state(thread_id)` on [line 77](../src/l10_6_local_server/__main__.py#L77) uses the id kept in a Python variable from section 2, and the thread is still there with its 4 messages: the new process loaded `.langgraph_api/` on start. This is a convenience of the dev runtime only; a deployed server keeps threads in Postgres, as the comment on lines 71-73 says.

## [test_app.py](../tests/test_app.py)

Offline tests: none of them starts `langgraph dev`, so they are fast and need no free port.

- [`test_factory_builds_graph_without_checkpointer`](../tests/test_app.py#L19-L25) checks the two promises of `make_graph`: no checkpointer of its own (line 23), and a new object on every call (line 25), since the server calls it again and again.
- [`test_langgraph_json_is_valid`](../tests/test_app.py#L28-L36) does not parse the JSON by hand. `validate_config_file` on [line 30](../tests/test_app.py#L30) is the CLI's own validator, the code `langgraph dev` and `langgraph build` run when they load the file, so a key it rejects fails here too. Lines 34-36 then split the graph spec at `:` and check that the file exists and the name is a callable in `graph.py`, which is the import the server will do.
- [`test_json_ticket_runs_in_process`](../tests/test_app.py#L39-L66) sends the same dict `ticket()` builds for the server to `make_graph().invoke(...)` in-process. [Line 62](../tests/test_app.py#L62) shows the conversion by `add_messages`: the first message comes back as a `HumanMessage`. In-process the result holds real message objects, so this test can check `.name` and `.content`, unlike the dicts the client gets over HTTP. `invoke` works here without a `thread_id` because the factory's graph has no checkpointer.
- [`test_running_server_refuses_busy_port`](../tests/test_app.py#L69-L82) binds a listening socket to port 0 (line 77), so the OS picks a free port, and that port is then busy for sure. [Line 75](../tests/test_app.py#L75) replaces `Popen` inside `server.py` with a function that fails the test, so the test proves both halves: `running_server` raises "already in use" and never tries to start a process.

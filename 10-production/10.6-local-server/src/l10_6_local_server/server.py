"""Start and stop `langgraph dev` for the live run.

A learner would type `langgraph dev` in a terminal instead; the live run
starts it as a child process so that it can run from start to finish alone.
"""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# region dev_command
# The lesson directory, where langgraph.json is. The server runs there and
# writes its .langgraph_api/ folder there.
APP_DIR = Path(__file__).resolve().parents[2]
LOG_FILE = APP_DIR / "server.log"

OFFLINE_ENV = {
    # The CLI otherwise sends a usage event.
    "LANGGRAPH_CLI_NO_ANALYTICS": "1",
    # The server otherwise asks pypi.org whether a newer version exists.
    "LANGGRAPH_NO_VERSION_CHECK": "true",
    # Keeps runs from being sent to LangSmith. No key is set anyway; this
    # makes it explicit.
    "LANGSMITH_TRACING": "false",
}


def dev_command(port: int) -> list[str]:
    """Return the `langgraph dev` command line for the given port."""
    return [
        # The CLI installed in the same venv as this Python.
        str(Path(sys.executable).with_name("langgraph")),
        "dev",
        "--port",
        str(port),
        # dev otherwise opens LangSmith Studio in a browser.
        "--no-browser",
        # The run does not edit code. By hand, leave reload on: the server
        # then restarts whenever a file changes.
        "--no-reload",
    ]


# endregion


# region port_check
def port_in_use(port: int) -> bool:
    """Tell whether something already listens on the local port."""
    # Needed because `langgraph dev` does not fail on a busy port: it logs
    # "Port N is already in use, using port M instead." and binds another
    # one, so the client would silently talk to whatever listens on N
    # (experiment 3).
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


# endregion


# region running_server
@contextmanager
def running_server(port: int) -> Iterator[str]:
    """Run `langgraph dev` on port and yield its URL; stop it on exit."""
    # Refuse before anything else: no log file, no process.
    if port_in_use(port):
        raise RuntimeError(f"port {port} is already in use; set LANGGRAPH_DEV_PORT to a free port")
    url = f"http://127.0.0.1:{port}"
    # The server's own log lines go to server.log (overwritten on every
    # start) so that the run's output stays readable.
    with LOG_FILE.open("w") as log:
        proc = subprocess.Popen(
            dev_command(port),
            cwd=APP_DIR,
            env={**os.environ, **OFFLINE_ENV},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        # The readiness wait is inside the try, so a failed start also stops
        # the process.
        try:
            deadline = time.monotonic() + 60
            while True:
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"langgraph dev exited with code {proc.returncode}; see {LOG_FILE.name}"
                    )
                try:
                    # GET /ok is the server's health route.
                    with urllib.request.urlopen(url + "/ok", timeout=1) as resp:
                        if resp.status == 200:
                            break
                except (urllib.error.URLError, ConnectionError):
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError(f"langgraph dev did not start; see {LOG_FILE.name}")
                time.sleep(0.2)
            yield url
        finally:
            # Like Ctrl+C in the terminal: the dev runtime saves .langgraph_api/
            # while it shuts down.
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


# endregion

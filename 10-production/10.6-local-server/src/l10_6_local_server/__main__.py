"""Live run of lesson 10.6: serve the support desk with `langgraph dev` and call it over HTTP."""

import os

from langgraph_sdk import get_sync_client

from l10_6_local_server.client import ASSISTANT, ask, reply_line
from l10_6_local_server.server import running_server

FIRST_TICKET = "Please refund invoice INV-1042"
SECOND_TICKET = "Where is my parcel?"
OTHER_TICKET = "Hello, do you have a dark mode?"


def main() -> None:
    """Start the server, run tickets on threads, restart it and read a thread back."""
    port = int(os.environ.get("LANGGRAPH_DEV_PORT", "2024"))

    with running_server(port) as url:
        with get_sync_client(url=url) as client:
            # region server_up
            print("== 1. langgraph dev serves the graph ==")
            print(f"  serving {url}")
            # Nobody created this assistant: the server made one per graph
            # in langgraph.json.
            for a in client.assistants.search(graph_id=ASSISTANT):
                print(
                    f"  assistant: {a['name']} (graph {a['graph_id']}, "
                    f"created by {a['metadata']['created_by']})"
                )
            # endregion

            # region thread_and_runs
            print()
            print("== 2. One thread, two runs ==")
            # No checkpointer and no thread_id config in our code: the thread
            # is a server object, the server keeps its checkpoints and passes
            # the thread id to every run. The second run sees the first
            # ticket because both runs share the thread.
            thread = client.threads.create()
            thread_id = thread["thread_id"]
            print(f"  thread created, status {thread['status']}")
            for text in (FIRST_TICKET, SECOND_TICKET):
                state = ask(client, thread_id, text)
                print(f"  run: {text!r} -> {state['category']}")
                print(f"    {reply_line(state)}")
                print(f"    the thread now holds {len(state['messages'])} messages")
            snapshot = client.threads.get_state(thread_id)
            print(
                f"  get_state: {len(snapshot['values']['messages'])} messages, "
                f"next {snapshot['next']}"
            )
            history = client.threads.get_history(thread_id, limit=100)
            print(f"  checkpoints in the history: {len(history)}")
            runs = client.runs.list(thread_id)
            print(f"  runs on the thread: {', '.join(r['status'] for r in runs)}")
            # endregion

            # region second_thread
            print()
            print("== 3. A second thread starts empty ==")
            other = client.threads.create()["thread_id"]
            state = ask(client, other, OTHER_TICKET)
            print(f"  run: {OTHER_TICKET!r} -> {state['category']}")
            print(f"    the new thread holds {len(state['messages'])} messages")
            # endregion

    # region restart
    print()
    print("== 4. Restart the server ==")
    # `langgraph dev` saves its in-memory data to .langgraph_api/ on shutdown
    # and loads it on start. That is a development convenience; a deployment
    # keeps threads in Postgres.
    with running_server(port) as url:
        with get_sync_client(url=url) as client:
            print("  server stopped and started again")
            snapshot = client.threads.get_state(thread_id)
            print(f"  the first thread still holds {len(snapshot['values']['messages'])} messages")
            print(f"    last reply: {reply_line(snapshot['values'])}")
    # endregion
    print()
    print("server stopped")


if __name__ == "__main__":
    main()

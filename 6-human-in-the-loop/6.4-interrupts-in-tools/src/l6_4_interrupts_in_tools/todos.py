"""The to-do list the agent works on, and its two tools.

Adding a task is free. Deleting one asks the user first: the delete_task tool
itself calls interrupt(), so the approval logic lives with the risky action,
not in the graph wiring.
"""

from collections import Counter
from typing import Annotated

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import interrupt

# region todo_store
TODO_LIST: dict[int, str] = {}
"""The to-do list, task number -> title.

It stands in for a database the tools change, so it lives outside the graph
state, like 6.3's MANAGER_INBOX.
"""

TOOL_RUNS: Counter[str] = Counter()
"""How many times each tool function has started; shows when a tool runs again on resume."""

ADDED_BY_CALL: dict[str, int] = {}
"""Tool call id -> the task number add_task created for it; makes add_task idempotent."""


def reset_todo_list() -> None:
    """Start from the same two tasks (used at import and by the tests)."""
    TODO_LIST.clear()
    TOOL_RUNS.clear()
    ADDED_BY_CALL.clear()
    TODO_LIST.update({1: "buy milk", 2: "call the bank"})


reset_todo_list()
# endregion


# region add_task
# Adding needs no approval, so this tool has no interrupt().
@tool
def add_task(title: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
    """Add a task to the to-do list."""
    # (The docstring above stays one line: @tool sends it whole to the model
    # as the tool description.)
    # tool_call_id is filled in by ToolNode with the id of the model's tool
    # call. It is hidden from the model: the schema the model sees has only
    # "title".
    TOOL_RUNS["add_task"] += 1
    # If this call shares a model reply with delete_task, the whole "tools"
    # node runs again on resume, and so does this function (Turn 4). The same
    # tool call keeps the same id, so the id is a natural idempotency key: the
    # second run adds nothing and returns the same text. This is 6.3's rule
    # (side effects before an interrupt must be safe to repeat), applied to a
    # SIBLING tool of the one that pauses.
    if tool_call_id not in ADDED_BY_CALL:
        task_id = max(TODO_LIST, default=0) + 1
        TODO_LIST[task_id] = title
        ADDED_BY_CALL[tool_call_id] = task_id
    return f"Added task {ADDED_BY_CALL[tool_call_id]}: {title}"


# endregion


# region delete_task
@tool
def delete_task(task_id: int) -> str:
    """Delete a task from the to-do list. The user must approve it first."""
    TOOL_RUNS["delete_task"] += 1
    # An unknown task needs no approval: the tool answers without pausing.
    if task_id not in TODO_LIST:
        return f"There is no task {task_id}."
    title = TODO_LIST[task_id]
    # The tool pauses the whole agent run here. The payload (JSON-serialisable,
    # stored with the checkpoint) tells the human what is about to happen.
    # interrupt() raises GraphInterrupt; ToolNode re-raises it (GraphBubbleUp)
    # before any error handling, so it never becomes an error ToolMessage, even
    # with handle_tool_errors=True. On resume ToolNode calls this tool again
    # from its first line (TOOL_RUNS shows 2 runs per approved delete), and
    # this time interrupt() returns the resume value.
    answer = interrupt(
        {
            "tool": "delete_task",
            "task_id": task_id,
            "title": title,
            "question": f"Delete task {task_id} {title!r}? Answer 'yes' to confirm.",
        }
    )
    # Only the exact answer "yes" deletes; anything else (any text, a dict,
    # "Yes") is a rejection. Failing closed also means a malformed answer can
    # never crash the tool after interrupt(): a crash here would leave the
    # thread stuck, because the saved resume value is replayed on every resume.
    if answer == "yes":
        del TODO_LIST[task_id]
        # Whatever the tool returns becomes the ToolMessage the model reads.
        return f"Deleted task {task_id}: {title}"
    # A rejection is a normal tool result (status "success"), not an error: it
    # carries the human's own words to the model, which can then answer the user.
    return f"Not deleted: the user answered {answer!r}"


# endregion

# The tools the agent offers to the model and runs in its "tools" node.
TOOLS = [add_task, delete_task]

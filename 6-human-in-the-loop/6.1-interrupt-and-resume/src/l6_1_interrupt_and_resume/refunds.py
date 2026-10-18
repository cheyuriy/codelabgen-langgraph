"""Refund requests above a limit wait for a manager's decision.

A small graph with one human-in-the-loop step: small refunds are approved by
policy, larger ones pause inside ``manager_review`` with ``interrupt()`` until
the caller resumes the thread with ``Command(resume=...)``.
"""

from typing import Literal, NotRequired, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

# region refund_state
REFUND_LIMIT = 100
"""Refunds up to this many whole dollars are approved without a human."""


class RefundState(TypedDict):
    """The state of one refund request.

    The caller only sends ``request_id`` and ``amount``. ``status`` and
    ``decided_by`` are written by the nodes, so while a request is paused
    for the manager its state has no ``status`` yet.
    """

    request_id: str
    amount: int
    status: NotRequired[str]
    decided_by: NotRequired[str]


# endregion


# region route_by_amount
def route_by_amount(state: RefundState) -> Literal["auto_approve", "manager_review"]:
    """Send refunds above REFUND_LIMIT to a manager, approve the rest by policy."""
    # The Literal return type tells LangGraph (and the graph drawing) which
    # nodes this conditional edge can lead to.
    if state["amount"] > REFUND_LIMIT:
        return "manager_review"
    return "auto_approve"


# endregion


# region auto_approve
def auto_approve(state: RefundState) -> dict[str, str]:
    """Approve a small refund without asking anyone."""
    return {"status": "approved", "decided_by": "policy"}


# endregion


# region manager_review
def manager_review(state: RefundState) -> dict[str, str]:
    """Pause the graph until a manager approves or rejects the refund.

    First run: ``interrupt()`` raises internally (a ``GraphInterrupt``) and the
    graph stops right here. LangGraph saves a checkpoint with this task still
    pending and the payload attached, and hands the payload to the caller.
    The payload must be JSON-serialisable, because it is stored with the
    checkpoint and sent to whoever answers it.

    Resume: when the caller invokes the same thread with
    ``Command(resume=...)``, this node runs again FROM ITS FIRST LINE (so the
    "started" print shows up twice), and this time ``interrupt()`` does not
    pause: it returns the value from ``Command(resume=...)``.
    Lesson 6.3 explains the rules this implies.
    """
    # Runs on the first run AND again on resume: the node restarts from the top.
    print(f"  [manager_review] started for {state['request_id']}")
    decision = interrupt(
        {
            "request_id": state["request_id"],
            "amount": state["amount"],
            "question": f"Approve a refund of ${state['amount']} for {state['request_id']}?",
        }
    )
    # Only reached on resume: `decision` is the human's answer, e.g. "approved".
    print(f"  [manager_review] resumed with {decision!r}")
    return {"status": decision, "decided_by": "manager"}


# endregion


# region build_graph
def build_graph(checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    """Build the refund graph: START routes by amount, both nodes end the run.

    interrupt() needs a checkpointer: the pause *is* a saved checkpoint, and
    resuming means loading that checkpoint again by thread_id. Without one the
    first run still returns the interrupt to the caller, but nothing is saved,
    so nothing can resume it.
    """
    builder = StateGraph(RefundState)
    builder.add_node("auto_approve", auto_approve)
    builder.add_node("manager_review", manager_review)
    builder.add_conditional_edges(START, route_by_amount)
    builder.add_edge("auto_approve", END)
    builder.add_edge("manager_review", END)
    return builder.compile(checkpointer=checkpointer)


# endregion
